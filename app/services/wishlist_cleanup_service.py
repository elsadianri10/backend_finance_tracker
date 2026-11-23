"""Durable cleanup for uploads no longer referenced by Wishlist."""
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError

from app.models.wishlist_model import WishlistBlobCleanup, WishlistPhoto
from app.services import wishlist_image_service as images

logger = logging.getLogger(__name__)


def enqueue(db, urls):
    jobs = [WishlistBlobCleanup(id=uuid4(), url=url) for url in set(urls)]
    db.add_all(jobs)
    return [job.id for job in jobs]


async def process(db, *, limit, job_ids=None, attempted_before=None):
    query = select(WishlistBlobCleanup)
    if job_ids is not None:
        query = query.where(WishlistBlobCleanup.id.in_(job_ids))
    if attempted_before is not None:
        query = query.where(or_(
            WishlistBlobCleanup.last_attempt_at.is_(None),
            WishlistBlobCleanup.last_attempt_at < attempted_before,
        ))
    jobs = list(await db.scalars(query.order_by(
        WishlistBlobCleanup.last_attempt_at.asc().nulls_first(),
        WishlistBlobCleanup.created_at,
        WishlistBlobCleanup.id,
    ).limit(limit).with_for_update(skip_locked=True)))
    urls = {job.url for job in jobs}
    if not urls:
        await db.commit()
        return 0, 0

    # A prior upload or a legacy duplicate may still reference an object.
    referenced = set(await db.scalars(select(WishlistPhoto.blob_url).where(WishlistPhoto.blob_url.in_(urls))))
    unused = urls - referenced
    failed = set()
    if unused:
        try:
            await images.delete_verified(unused)
        except HTTPException:
            failed = unused
            logger.warning('Wishlist Blob cleanup deferred')

    attempted_at = datetime.now(timezone.utc)
    for job in jobs:
        if job.url in failed:
            job.last_attempt_at = attempted_at
        else:
            await db.delete(job)
    failed_count = sum(job.url in failed for job in jobs)
    await db.commit()
    return len(jobs), failed_count


async def after_commit(db, job_ids):
    if job_ids:
        try:
            await process(db, limit=20, job_ids=job_ids)
        except SQLAlchemyError:
            await db.rollback()
            logger.warning('Wishlist Blob cleanup queue will be retried')


async def after_failed_upload(db, urls):
    if urls:
        try:
            jobs = enqueue(db, urls)
            await db.commit()
        except SQLAlchemyError:
            await db.rollback()
            logger.error('Wishlist Blob cleanup could not be queued after failed upload')
        else:
            await after_commit(db, jobs)

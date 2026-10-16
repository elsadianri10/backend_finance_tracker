"""Verify 022 and competing reservations in a disposable PostgreSQL schema only."""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from check_debt_installment_migration import engine, snapshot
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User, Wishlist, WishlistGroup, WishlistItem, WishlistReservation
from app.services import wishlist_service as service
from fastapi import HTTPException
from sqlalchemy import select, func

NEW = ('wishlist_reservations', 'wishlist_photos', 'wishlist_items', 'wishlist_groups', 'wishlists')


async def check():
    schema = 'wishlist_test_' + uuid4().hex
    async with engine.connect() as connection:
        db = (await connection.get_raw_connection()).driver_connection
        await db.execute(f'CREATE SCHEMA "{schema}"; SET search_path TO "{schema}"')
        try:
            baseline = (ROOT/'database/000_init.sql').read_text(encoding='utf-8')
            await db.execute(baseline.replace("set_config('finance_tracker.reset', 'on', true)", "set_config('finance_tracker.reset', 'off', true)"))
            await db.execute('DROP TABLE ' + ','.join(NEW))
            users = [uuid4() for _ in range(3)]
            for index, user_id in enumerate(users):
                await db.execute("INSERT INTO users(id,google_sub,email,name,last_login_at) VALUES($1,$2,'synthetic@example.test','Synthetic',NOW())", user_id, 'wishlist-synthetic-'+str(index))
            await db.execute("INSERT INTO debts(id,user_id,kind,person_name,principal,transaction_date,interest_type,interest_rate) VALUES($1,$2,'DEBT','Synthetic',1000,'2026-10-01','NONE',0)", uuid4(), users[0])
            tables = [r['tablename'] for r in await db.fetch('SELECT tablename FROM pg_tables WHERE schemaname=current_schema() ORDER BY tablename')]
            before = await snapshot(db, tables)
            migration = (ROOT/'database/022_wishlists.sql').read_text(encoding='utf-8')
            await db.execute(migration)
            await db.execute(migration)
            assert before == await snapshot(db, tables)
            for table in NEW:
                assert await db.fetchval(f'SELECT COUNT(*) FROM {table}') == 0
            await db.execute('CREATE TABLE wishlist_test_sentinel(value INTEGER); INSERT INTO wishlist_test_sentinel VALUES(42)')
            async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                row = Wishlist(user_id=users[0], name='Synthetic', kind='things')
                session.add(row); await session.flush()
                group = WishlistGroup(wishlist_id=row.id, name='Synthetic')
                session.add(group); await session.flush()
                item = WishlistItem(group_id=group.id, name='One only')
                session.add(item); await session.commit()
                owner = await session.get(User, users[0])
                token = (await service.share(row.id, owner, session))['Token']
                list_id, item_id = row.id, item.id
            async def compete(user_id):
                async with engine.connect() as conn:
                    await conn.exec_driver_sql(f'SET search_path TO "{schema}"')
                    await conn.commit()
                    async with AsyncSession(bind=conn, expire_on_commit=False) as session:
                        user = await session.get(User, user_id)
                        try:
                            await service.reserve(None, token, item_id, False, user, session)
                            return 200
                        except HTTPException as error:
                            await session.rollback()
                            return error.status_code
            assert sorted(await asyncio.gather(*(compete(user_id) for user_id in users[1:]))) == [200, 409]
            async with AsyncSession(bind=connection) as session:
                reservation = await session.get(WishlistReservation, item_id)
                assert reservation is not None
                loser = next(u for u in users[1:] if u != reservation.user_id)
                user = await session.get(User, loser)
                try:
                    await service.reserve(None, token, item_id, True, user, session)
                    raise AssertionError('Cannot cancel another person reservation')
                except HTTPException as error:
                    assert error.status_code == 403
                    await session.rollback()
            assert before == await snapshot(db, tables)
            await db.execute(baseline)
            for table in NEW:
                assert await db.fetchval(f'SELECT COUNT(*) FROM {table}') == 0
            assert await db.fetchval('SELECT value FROM wishlist_test_sentinel') == 42
            print('PASS: additive/repeated upgrade preserves records; real PostgreSQL concurrent reservation has one winner; other user cannot cancel; baseline/reset works only in synthetic schema.')
        finally:
            await db.execute('ROLLBACK; SET search_path TO public')
            await db.execute(f'DROP SCHEMA "{schema}" CASCADE')
    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(check())

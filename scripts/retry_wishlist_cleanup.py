"""Retry pending Wishlist Blob deletions without printing private URLs."""
import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def run(limit: int) -> int:
    load_dotenv(ROOT / '.env')
    from app.config.db_config import async_session, engine
    from app.services.wishlist_cleanup_service import process

    started_at = datetime.now(timezone.utc)
    handled = failed = 0
    try:
        async with async_session() as db:
            for _ in range(limit):
                count, deferred = await process(db, limit=1, attempted_before=started_at)
                if not count:
                    break
                handled += count
                failed += deferred
    except (SQLAlchemyError, OSError) as error:
        print(f'Pembersihan Wishlist gagal dijalankan ({type(error).__name__}).', file=sys.stderr)
        return 1
    finally:
        await engine.dispose()
    print(f'Pembersihan Wishlist: {handled - failed} selesai, {failed} perlu dicoba ulang.')
    return int(failed > 0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error('--limit must be between 1 and 100')
    sys.exit(asyncio.run(run(args.limit)))

"""Apply additive 028 locally, with a private snapshot and full old-row comparison before commit."""
import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
load_dotenv(ROOT/'.env')
from check_debt_installment_migration import engine, snapshot

async def run(apply):
    try:
        if engine.url.host not in {'localhost','127.0.0.1','::1'}:
            raise ValueError('This local-only helper refuses remote databases. Use reviewed migration 028 for hosted environments.')
        if not apply:
            print('Read-only: database is local. Pass --apply to back up existing records and apply additive migration 028.')
            return
        async with engine.connect() as connection:
            db=(await connection.get_raw_connection()).driver_connection
            tables=[r['tablename'] for r in await db.fetch('SELECT tablename FROM pg_tables WHERE schemaname=current_schema() ORDER BY tablename')]
            before=await snapshot(db,tables)
            backup=ROOT/'.migration-backups';backup.mkdir(exist_ok=True)
            filename=backup/('subscriptions-028-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
            filename.write_text(json.dumps(before,default=str,ensure_ascii=False,indent=2),encoding='utf-8')
            sql=(ROOT/'database/028_subscriptions.sql').read_text(encoding='utf-8')
            sql=sql.replace('BEGIN;','',1).rsplit('COMMIT;',1)[0]
            async with db.transaction():
                await db.execute(sql)
                if before!=await snapshot(db,tables):
                    raise ValueError('Existing records changed; transaction rolled back.')
            print('Migration 028 applied locally. All pre-existing table rows are identical. Private snapshot stored in .migration-backups.')
    finally:
        await engine.dispose()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true')
    asyncio.run(run(parser.parse_args().apply))

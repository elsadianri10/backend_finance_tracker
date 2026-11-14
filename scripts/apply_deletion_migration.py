"""Apply additive migration 030 locally after a private snapshot and row equality check."""
import argparse,asyncio,json,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tests'))
from check_debt_installment_migration import engine,snapshot
async def run(apply=False):
    try:
        if engine.url.host not in {'localhost','127.0.0.1','::1'}:raise RuntimeError('Local-only helper refuses hosted databases')
        if not apply:print('Read-only: pass --apply for local migration 030');return
        async with engine.connect() as conn:
            db=(await conn.get_raw_connection()).driver_connection
            tables=[r['tablename'] for r in await db.fetch('SELECT tablename FROM pg_tables WHERE schemaname=current_schema() ORDER BY tablename')]
            before=await snapshot(db,tables)
            folder=ROOT/'.migration-backups';folder.mkdir(exist_ok=True)
            (folder/('deletions-030-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')).write_text(json.dumps(before,default=str),encoding='utf-8')
            sql=(ROOT/'database/030_account_deletions.sql').read_text(encoding='utf-8').replace('BEGIN;','',1).rsplit('COMMIT;',1)[0]
            async with db.transaction():
                await db.execute(sql)
                if before!=await snapshot(db,tables):raise RuntimeError('Old rows differ; migration rolled back')
            print('PASS: migration 030 applied locally, every pre-existing table row identical. No user account deleted.')
    finally:await engine.dispose()
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');asyncio.run(run(parser.parse_args().apply))

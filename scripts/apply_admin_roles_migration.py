"""Apply migration 031 locally with a private snapshot and verification of every old field."""
import argparse,asyncio,json,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tests'))
from check_debt_installment_migration import engine,snapshot
async def run(apply=False):
    try:
        if engine.url.host not in {'localhost','127.0.0.1','::1'}:raise RuntimeError('Local-only helper refuses hosted databases')
        if not apply:print('Read-only: pass --apply for local migration 031');return
        async with engine.connect() as conn:
            db=(await conn.get_raw_connection()).driver_connection
            tables=[r['tablename'] for r in await db.fetch('SELECT tablename FROM pg_tables WHERE schemaname=current_schema() ORDER BY tablename')]
            before=await snapshot(db,tables)
            folder=ROOT/'.migration-backups';folder.mkdir(exist_ok=True)
            (folder/('admin-roles-031-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')).write_text(json.dumps(before,default=str),encoding='utf-8')
            sql=(ROOT/'database/031_user_admin_roles.sql').read_text(encoding='utf-8').replace('BEGIN;','',1).rsplit('COMMIT;',1)[0]
            async with db.transaction():
                await db.execute(sql);after=await snapshot(db,tables)
                expected={row['id']:1 if row['email'].strip().casefold()=='elsadianri10@gmail.com' else row.get('admin_f',0) for row in before['users']}
                for row in after['users']:
                    if row.pop('admin_f')!=expected[row['id']]:raise RuntimeError('Unexpected admin assignment')
                for row in before['users']:row.pop('admin_f',None)
                if before!=after:raise RuntimeError('Old fields differ; migration rolled back')
            print('PASS: 031 applied locally; only intended admin flags changed. All pre-existing financial and personal fields identical; Pro access preserved.')
    finally:await engine.dispose()
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');asyncio.run(run(parser.parse_args().apply))

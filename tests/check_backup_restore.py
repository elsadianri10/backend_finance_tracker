"""Local pg_dump/pg_restore drill using exclusively random synthetic schemas."""
import asyncio
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from check_debt_installment_migration import engine,snapshot

async def check():
    url=engine.url
    if url.host not in {'localhost','127.0.0.1','::1'}:raise RuntimeError('Restore drill only permits a loopback database')
    schema='restore_drill_'+uuid4().hex
    saved=schema+'_saved'
    assert all(re.fullmatch(r'restore_drill_[0-9a-f]{32}(?:_saved)?',s) for s in (schema,saved))
    bin_path=Path(os.getenv('PG_BIN',r'C:/Program Files/PostgreSQL/16/bin'))
    env=os.environ | {'PGHOST':url.host,'PGPORT':str(url.port or 5432),'PGUSER':url.username or '', 'PGPASSWORD':url.password or '', 'PGDATABASE':url.database or ''}
    async with engine.connect() as connection:
        db=(await connection.get_raw_connection()).driver_connection
        await db.execute(f'CREATE SCHEMA "{schema}"; SET search_path TO "{schema}"')
        try:
            baseline=(ROOT/'database/000_init.sql').read_text(encoding='utf-8')
            await db.execute(baseline)
            user,saving=uuid4(),uuid4()
            await db.execute("INSERT INTO users(id,google_sub,email,name,last_login_at) VALUES($1,'restore-synthetic','synthetic@example.test','Synthetic',NOW())",user)
            await db.execute("INSERT INTO savings(id,user_id,kind,name,opening_amount,start_date,notes) VALUES($1,$2,'CASH','Synthetic restore',1234567,'2026-11-01','restore drill')",saving,user)
            tables=[row['tablename'] for row in await db.fetch('SELECT tablename FROM pg_tables WHERE schemaname=current_schema() ORDER BY tablename')]
            before=await snapshot(db,tables)
            with tempfile.TemporaryDirectory(prefix='finance-synthetic-restore-') as temp:
                dump=Path(temp)/'synthetic.dump'
                def run(tool,args):
                    result=subprocess.run([str(bin_path/(tool+'.exe')),*args],env=env,capture_output=True,text=True)
                    if result.returncode:raise RuntimeError(tool+' failed; inspect local PostgreSQL client/server compatibility (no credentials logged)')
                await asyncio.to_thread(run,'pg_dump',['--format=custom','--no-owner','--no-privileges','--schema',schema,'--file',str(dump)])
                await db.execute(f'ALTER SCHEMA "{schema}" RENAME TO "{saved}"')
                await asyncio.to_thread(run,'pg_restore',['--single-transaction','--exit-on-error','--no-owner','--no-privileges','--dbname',url.database,str(dump)])
                await db.execute(f'SET search_path TO "{schema}"')
                assert before==await snapshot(db,tables),'Restored rows differ'
                constraints=await db.fetchval("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON c.connamespace=n.oid WHERE n.nspname=$1",schema)
                original=await db.fetchval("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON c.connamespace=n.oid WHERE n.nspname=$1",saved)
                assert constraints==original and constraints>0
            print('PASS: local custom dump restored all synthetic table rows and constraints exactly; application schema untouched.')
        finally:
            await db.execute('ROLLBACK');await db.execute('SET search_path TO public')
            for target in (schema,saved):await db.execute(f'DROP SCHEMA IF EXISTS "{target}" CASCADE')
    await engine.dispose()

if __name__=='__main__':asyncio.run(check())

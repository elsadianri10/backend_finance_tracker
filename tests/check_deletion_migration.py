import asyncio,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from check_debt_installment_migration import engine,snapshot
from synthetic_database import reset_synthetic_schema
async def check():
    schema='deletion_test_'+uuid4().hex
    async with engine.connect() as conn:
        db=(await conn.get_raw_connection()).driver_connection
        await db.execute(f'CREATE SCHEMA "{schema}"; SET search_path TO "{schema}"')
        try:
            baseline=(ROOT/'database/000_init.sql').read_text(encoding='utf-8')
            keep=baseline
            await db.execute(keep)
            await db.execute('DROP TABLE account_deletion_blobs; DROP TABLE account_deletions')
            user=uuid4();await db.execute("INSERT INTO users(id,google_sub,email,name,last_login_at) VALUES($1,'synthetic-delete','synthetic@example.test','Synthetic',now())",user)
            tables=[r['tablename'] for r in await db.fetch('SELECT tablename FROM pg_tables WHERE schemaname=current_schema() ORDER BY tablename')]
            before=await snapshot(db,tables)
            sql=(ROOT/'database/030_account_deletions.sql').read_text(encoding='utf-8');await db.execute(sql);await db.execute(sql)
            assert before==await snapshot(db,tables)
            await db.execute(keep);assert before==await snapshot(db,tables)
            await reset_synthetic_schema(db, schema);assert await db.fetchval('SELECT COUNT(*) FROM users')==0
            print('PASS: migration 030 upgrade/repeat preserves all pre-existing fields; reset only in synthetic schema.')
        finally:
            await db.execute('ROLLBACK');await db.execute('SET search_path TO public');await db.execute(f'DROP SCHEMA "{schema}" CASCADE')
    await engine.dispose()
if __name__=='__main__':asyncio.run(check())

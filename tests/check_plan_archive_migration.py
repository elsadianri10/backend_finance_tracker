import asyncio
import sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from check_debt_installment_migration import engine,snapshot
from synthetic_database import reset_synthetic_schema

async def check():
    schema='plan_archive_test_'+uuid4().hex
    async with engine.connect() as connection:
        db=(await connection.get_raw_connection()).driver_connection
        await db.execute(f'CREATE SCHEMA "{schema}"; SET search_path TO "{schema}"')
        try:
            base=(ROOT/'database/000_init.sql').read_text(encoding='utf-8')
            keep=base
            await db.execute(keep)
            await db.execute('ALTER TABLE bank_accounts DROP COLUMN archived; ALTER TABLE savings DROP COLUMN archived')
            user,bank,saving=uuid4(),uuid4(),uuid4()
            await db.execute("INSERT INTO users(id,google_sub,email,name,last_login_at) VALUES($1,'archive-test','synthetic@example.test','Synthetic',NOW())",user)
            await db.execute("INSERT INTO bank_accounts(id,user_id,platform_id,account_number_encrypted,card_number_encrypted,valid_thru,admin_fee,others_fee) VALUES($1,$2,1,'synthetic','synthetic','2029-12',100,200)",bank,user)
            await db.execute("INSERT INTO savings(id,user_id,kind,name,opening_amount,start_date,notes,bank_account_id) VALUES($1,$2,'CASH','Synthetic',1000000,'2026-11-01','',$3)",saving,user,bank)
            tables=[r['tablename'] for r in await db.fetch('SELECT tablename FROM pg_tables WHERE schemaname=current_schema() ORDER BY tablename')]
            before=await snapshot(db,tables)
            sql=(ROOT/'database/029_plan_archives.sql').read_text(encoding='utf-8')
            await db.execute(sql);await db.execute(sql)
            after=await snapshot(db,tables)
            for table in ('bank_accounts','savings'):
                for row in after[table]:assert row.pop('archived') is False
            assert before==after
            await db.execute('UPDATE bank_accounts SET archived=true; UPDATE savings SET archived=true')
            populated=await snapshot(db,tables)
            await db.execute(sql);await db.execute(keep)
            assert populated==await snapshot(db,tables)
            await reset_synthetic_schema(db, schema)
            assert await db.fetchval('SELECT COUNT(*) FROM users')==0
            print('PASS: additive/repeated 029 preserves all old fields and balances; archive flags survive repeat/baseline; reset only in synthetic schema.')
        finally:
            await db.execute('ROLLBACK');await db.execute('SET search_path TO public');await db.execute(f'DROP SCHEMA "{schema}" CASCADE')
    await engine.dispose()
if __name__=='__main__':asyncio.run(check())

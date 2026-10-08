"""Verify 010 -> 011 with synthetic rows, then upgrade locally without reset."""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4
from dotenv import load_dotenv
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv('.env')
from app.config.db_config import engine


async def main():
    migration = Path('database/011_savings_precious_metals.sql').read_text(encoding='utf-8')
    async with engine.connect() as connection:
        raw = await connection.get_raw_connection()
        db = raw.driver_connection
        schema='metal_migration_test_'+uuid4().hex
        original_schema=await db.fetchval('SELECT current_schema()')
        await db.execute(f'CREATE SCHEMA "{schema}"')
        try:
            await db.execute(f'SET search_path TO "{schema}"')
            await db.execute('CREATE TABLE users(id UUID PRIMARY KEY); CREATE TABLE bank_accounts(id UUID PRIMARY KEY);')
            await db.execute(Path('database/010_savings.sql').read_text(encoding='utf-8'))
            user_id, item_id = uuid4(), uuid4()
            await db.execute('INSERT INTO users VALUES($1)', user_id)
            await db.execute("INSERT INTO savings(id,user_id,kind,name,opening_amount,start_date,weight_per_piece,pieces,price_per_gram,notes) VALUES($1,$2,'GOLD','Synthetic',10,'2026-10-01',5,2,1700000,'')",item_id,user_id)
            await db.execute("INSERT INTO saving_movements(id,saving_id,request_id,sequence,direction,amount,movement_date,notes) VALUES($1,$2,$3,1,'ADD',0.5,'2026-10-08','')",uuid4(),item_id,uuid4())
            before=[dict(row) for row in await db.fetch('SELECT * FROM savings ORDER BY id')]
            movements=await db.fetch('SELECT * FROM saving_movements ORDER BY id')
            await db.execute(migration)
            after=[dict(row) for row in await db.fetch('SELECT * FROM savings ORDER BY id')]
            assert all(row.pop('metal_type')=='GOLD' for row in after)
            assert after==before
            assert movements==await db.fetch('SELECT * FROM saving_movements ORDER BY id')
        finally:
            await db.execute('ROLLBACK')
            await db.execute(f'SET search_path TO "{original_schema}"')
            await db.execute(f'DROP SCHEMA "{schema}" CASCADE')
        exists=await db.fetchval("SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='savings' AND column_name='metal_type')")
        if exists:
            print('PASS synthetic 010 -> 011; local 011 already applied, no changes.')
        else:
            tables=['users','wallet_providers','bank_accounts','billing_accounts','billing_transactions','billing_installments','debts','debt_payments','savings','saving_movements']
            before={table:[dict(row) for row in await db.fetch(f'SELECT * FROM {table} ORDER BY id')] for table in tables}
            await db.execute(migration)
            after={table:[dict(row) for row in await db.fetch(f'SELECT * FROM {table} ORDER BY id')] for table in tables}
            for row in after['savings']:
                assert row.pop('metal_type')==('GOLD' if row['kind']=='GOLD' else None)
            assert before==after
            print('PASS synthetic upgrade; APPLIED 011 with all existing records/quantities/history preserved. Old gold classified as GOLD.')
    await engine.dispose()

if __name__=='__main__':
    asyncio.run(main())

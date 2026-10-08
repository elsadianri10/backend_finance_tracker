"""Verify migration in an isolated schema; optionally upgrade the actual schema without resets."""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4
from dotenv import load_dotenv
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
load_dotenv('.env')
from app.config.db_config import engine


async def main():
    async with engine.connect() as connection:
        raw=await connection.get_raw_connection();db=raw.driver_connection
        schema='wallet_test_'+uuid4().hex
        await db.execute(f'CREATE SCHEMA "{schema}"')
        try:
            await db.execute(f'SET search_path TO "{schema}"')
            await db.execute('CREATE TABLE users(id UUID PRIMARY KEY)')
            for number in range(1,9):
                file=next(Path('database').glob(f'{number:03d}_*.sql'))
                await db.execute(file.read_text(encoding='utf-8'))
                if number==7:
                    await db.execute("INSERT INTO billing_platforms(id,name,is_active) VALUES(99,'Custom Bank',false)")
                    user,account=uuid4(),uuid4()
                    await db.execute('INSERT INTO users(id) VALUES($1)',user)
                    await db.execute("INSERT INTO billing_accounts(id,user_id,platform_id,platform_type,has_fixed_bill_date) VALUES($1,$2,99,'PAY_LATER',false)",account,user)
            assert await db.fetchval("SELECT to_regclass('billing_platforms')") is None
            assert await db.fetchval('SELECT name FROM wallet_providers WHERE id=99')=='Custom Bank'
            assert await db.fetchval('SELECT platform_id FROM billing_accounts WHERE id=$1',account)==99
            assert await db.fetchval('SELECT bank_f FROM wallet_providers WHERE id=1')==1
            assert await db.fetchval('SELECT bank_f FROM wallet_providers WHERE id=3')==0
            print('PASS: 001-008 migration preserves custom providers, account foreign keys and IDs; BCA/BRI BankF=1.')
        finally:
            await db.execute('ROLLBACK');await db.execute('SET search_path TO public');await db.execute(f'DROP SCHEMA "{schema}" CASCADE')
        if '--apply' in sys.argv:
            old=await db.fetchval("SELECT to_regclass('billing_platforms')")
            new=await db.fetchval("SELECT to_regclass('wallet_providers')")
            if old and not new:
                tables=['users','billing_accounts','billing_transactions','billing_installments','debts','debt_payments']
                counts={table:await db.fetchval(f'SELECT COUNT(*) FROM {table}') for table in tables}
                providers=await db.fetch('SELECT id,name,is_active FROM billing_platforms ORDER BY id')
                await db.execute(Path('database/008_wallet_providers_bank_accounts.sql').read_text(encoding='utf-8'))
                assert providers==await db.fetch('SELECT id,name,is_active FROM wallet_providers ORDER BY id')
                assert counts=={table:await db.fetchval(f'SELECT COUNT(*) FROM {table}') for table in tables}
                assert await db.fetchval('SELECT COUNT(*) FROM bank_accounts')==0
                print('APPLIED 008: renamed provider table and created empty bank_accounts; all existing data counts/provider values unchanged.')
            elif new and not old: print('008 already applied; no changes.')
            else: raise RuntimeError('Unexpected schema; migration was not applied.')
    await engine.dispose()


if __name__=='__main__':asyncio.run(main())

"""Check fee migration in a disposable schema, then apply without resetting data."""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv('.env')
from app.config.db_config import engine


async def main():
    sql = Path('database/013_billing_account_fees.sql').read_text(encoding='utf-8')
    async with engine.connect() as connection:
        raw = await connection.get_raw_connection()
        db = raw.driver_connection
        schema = 'fee_migration_test_' + uuid4().hex
        original = await db.fetchval('SELECT current_schema()')
        await db.execute(f'CREATE SCHEMA "{schema}"')
        try:
            await db.execute(f'SET search_path TO "{schema}"')
            await db.execute('CREATE TABLE billing_accounts(id UUID PRIMARY KEY, name TEXT);')
            await db.execute("INSERT INTO billing_accounts VALUES($1,'Synthetic')", uuid4())
            before = [dict(row) for row in await db.fetch('SELECT * FROM billing_accounts ORDER BY id')]
            await db.execute(sql)
            after = [dict(row) for row in await db.fetch('SELECT * FROM billing_accounts ORDER BY id')]
            for row in after:
                assert row.pop('monthly_fee') == 0 and row.pop('payment_fee') == 0
            assert before == after
            await db.execute('UPDATE billing_accounts SET monthly_fee=15000,payment_fee=7500')
            for invalid in ('-1', '1000000000001'):
                try:
                    await db.execute(f'UPDATE billing_accounts SET payment_fee={invalid}')
                except Exception as error:
                    assert getattr(error, 'sqlstate', None) == '23514'
                else:
                    raise AssertionError('Invalid fee accepted')
        finally:
            await db.execute('ROLLBACK')
            await db.execute(f'SET search_path TO "{original}"')
            await db.execute(f'DROP SCHEMA "{schema}" CASCADE')
        exists = await db.fetchval("SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='billing_accounts' AND column_name='monthly_fee')")
        if not exists:
            tables = ['users','wallet_providers','bank_accounts','billing_accounts','billing_transactions','billing_installments','debts','debt_payments','savings','saving_movements']
            before = {table: [dict(row) for row in await db.fetch(f'SELECT * FROM {table} ORDER BY id')] for table in tables}
            await db.execute(sql)
            after = {table: [dict(row) for row in await db.fetch(f'SELECT * FROM {table} ORDER BY id')] for table in tables}
            for row in after['billing_accounts']:
                assert row.pop('monthly_fee') == 0 and row.pop('payment_fee') == 0
            assert before == after
            print('PASS: applied 013; all existing data preserved, account fees default 0.')
        else:
            print('PASS: synthetic fee upgrade; local 013 already present, no changes.')
    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())

"""Apply additive migration 014 and verify existing records are unchanged."""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4
from dotenv import load_dotenv
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv('.env')
from app.config.db_config import engine


async def main():
    sql = Path('database/014_split_bills.sql').read_text(encoding='utf-8')
    async with engine.connect() as connection:
        raw = await connection.get_raw_connection()
        db = raw.driver_connection
        schema = 'split_migration_test_' + uuid4().hex
        original = await db.fetchval('SELECT current_schema()')
        await db.execute(f'CREATE SCHEMA "{schema}"')
        try:
            await db.execute(f'SET search_path TO "{schema}"')
            await db.execute('CREATE TABLE users(id UUID PRIMARY KEY)')
            await db.execute(sql)
            user_id = uuid4()
            await db.execute('INSERT INTO users VALUES($1)', user_id)
            await db.execute("INSERT INTO split_bill_groups(id,user_id,document,version) VALUES($1,$2,'{}',1)",uuid4(),user_id)
            assert await db.fetchval('SELECT count(*) FROM split_bill_groups') == 1
        finally:
            await db.execute('ROLLBACK')
            await db.execute(f'SET search_path TO "{original}"')
            await db.execute(f'DROP SCHEMA "{schema}" CASCADE')
        exists = await db.fetchval("SELECT to_regclass('split_bill_groups') IS NOT NULL")
        if not exists:
            tables = ['users','wallet_providers','bank_accounts','billing_accounts','billing_transactions','billing_installments','debts','debt_payments','savings','saving_movements']
            before = {table: await db.fetch(f'SELECT * FROM {table} ORDER BY id') for table in tables}
            await db.execute(sql)
            after = {table: await db.fetch(f'SELECT * FROM {table} ORDER BY id') for table in tables}
            assert before == after
            print('PASS: applied 014, all existing records preserved.')
        else:
            print('PASS: synthetic migration; local 014 already present, unchanged.')
    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())

"""Additive Savings migration, preserving all existing data; never runs reset."""
import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv('.env')
from app.config.db_config import engine


async def main():
    async with engine.connect() as connection:
        raw = await connection.get_raw_connection()
        db = raw.driver_connection
        if await db.fetchval("SELECT to_regclass('savings') IS NOT NULL"):
            print('010 already applied; no changes.')
        else:
            tables = ['users', 'wallet_providers', 'bank_accounts', 'billing_accounts', 'billing_transactions', 'billing_installments', 'debts', 'debt_payments']
            before = {t: await db.fetch(f'SELECT * FROM {t} ORDER BY id') for t in tables}
            await db.execute(Path('database/010_savings.sql').read_text(encoding='utf-8'))
            assert before == {t: await db.fetch(f'SELECT * FROM {t} ORDER BY id') for t in tables}
            assert await db.fetchval('SELECT COUNT(*) FROM savings') == 0
            assert await db.fetchval('SELECT COUNT(*) FROM saving_movements') == 0
            print('APPLIED 010: all existing records unchanged; empty savings and saving_movements created.')
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(main())

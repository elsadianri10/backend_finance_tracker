"""Additive upgrade only, with before/after checks; never resets application data."""
import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
load_dotenv('.env')
from app.config.db_config import engine

async def main():
    async with engine.connect() as connection:
        raw=await connection.get_raw_connection();db=raw.driver_connection
        available=await db.fetchval("SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='debts' AND column_name='installment_count')")
        if available:
            print('009 already applied; no changes.')
        else:
            tables=['wallet_providers','users','bank_accounts','billing_accounts','billing_transactions','billing_installments','debts','debt_payments']
            counts={t:await db.fetchval(f'SELECT COUNT(*) FROM {t}') for t in tables}
            old=await db.fetch('SELECT id,kind,person_name,principal,transaction_date,due_date,interest_type,interest_rate,notes FROM debts ORDER BY id')
            await db.execute(Path('database/009_debt_sources_installments.sql').read_text(encoding='utf-8'))
            assert counts=={t:await db.fetchval(f'SELECT COUNT(*) FROM {t}') for t in tables}
            assert old==await db.fetch('SELECT id,kind,person_name,principal,transaction_date,due_date,interest_type,interest_rate,notes FROM debts ORDER BY id')
            assert await db.fetchval('SELECT COUNT(*) FROM debts WHERE installment_count<>0 OR source_bank_account_id IS NOT NULL')==0
            print('APPLIED 009: all existing table counts and debt terms unchanged; old records remain without an installment plan.')
    await engine.dispose()
if __name__=='__main__':asyncio.run(main())

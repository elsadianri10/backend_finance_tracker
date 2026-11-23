"""033 upgrade and repeat verification only in an isolated synthetic schema."""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4
import asyncpg
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from check_debt_installment_migration import engine, snapshot

async def check():
    schema = 'same_bank_test_' + uuid4().hex
    async with engine.connect() as conn:
        db = (await conn.get_raw_connection()).driver_connection
        await db.execute(f'CREATE SCHEMA "{schema}"; SET search_path TO "{schema}"')
        try:
            await db.execute("""CREATE TABLE ledger_transactions (
                id UUID PRIMARY KEY, kind VARCHAR(10) NOT NULL,
                amount BIGINT NOT NULL CHECK(amount > 0), source_bank_id UUID, destination_bank_id UUID,
                CONSTRAINT ck_ledger_kind CHECK(kind IN ('income','expense','transfer')),
                CONSTRAINT ck_ledger_distinct_banks CHECK(source_bank_id IS NULL OR destination_bank_id IS NULL OR source_bank_id <> destination_bank_id))""")
            first, second = uuid4(), uuid4()
            await db.execute("INSERT INTO ledger_transactions VALUES($1,'transfer',500,$2,$3)", uuid4(), first, second)
            before = await snapshot(db, ['ledger_transactions'])
            try:
                await db.execute("INSERT INTO ledger_transactions VALUES($1,'transfer',200,$2,$2)", uuid4(), first)
            except asyncpg.CheckViolationError:
                pass
            else:
                raise AssertionError('Old constraint did not block same-account transfer')
            sql = (ROOT/'database/033_allow_same_account_transfers.sql').read_text(encoding='utf-8')
            await db.execute(sql)
            await db.execute(sql)
            assert before == await snapshot(db, ['ledger_transactions'])
            await db.execute("INSERT INTO ledger_transactions VALUES($1,'transfer',200,$2,$2)", uuid4(), first)
            after = await snapshot(db, ['ledger_transactions'])
            await db.execute(sql)
            assert after == await snapshot(db, ['ledger_transactions'])
            for kind, amount in [('transfer', 0), ('invalid', 200)]:
                try:
                    await db.execute('INSERT INTO ledger_transactions VALUES($1,$2,$3,$4,$4)', uuid4(), kind, amount, first)
                except asyncpg.CheckViolationError:
                    pass
                else:
                    raise AssertionError('Unrelated validation was removed')
            print('PASS: 033 removes old block; preserves all existing rows, repeats safely and keeps amount/kind checks')
        finally:
            await db.execute('ROLLBACK')
            await db.execute('SET search_path TO public')
            await db.execute(f'DROP SCHEMA "{schema}" CASCADE')
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(check())

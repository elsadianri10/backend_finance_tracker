"""Check 018 in an isolated schema; --apply compares all existing records."""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env')
from app.config.db_config import engine
from app.models import Base


def baseline_017(sql):
    for line in ('\tsaving_id UUID,\n', '\tsaving_movement_id UUID,\n',
                 '\tCONSTRAINT uq_ledger_saving_movement UNIQUE (saving_movement_id),\n'):
        sql = sql.replace(line, '')
    sql = sql.replace(',\n\tFOREIGN KEY(saving_id) REFERENCES savings (id)', '')
    sql = sql.replace(',\n\tFOREIGN KEY(saving_movement_id) REFERENCES saving_movements (id)', '')
    for field in ("('ledger_transactions', 'saving_movement_id'),", "('routine_plans', 'saving_id'),"):
        sql = sql.replace('        ' + field + '\n', '')
    return sql


async def check(apply=False):
    schema = None
    async with engine.connect() as conn:
        raw = (await conn.get_raw_connection()).driver_connection
        try:
            if not apply:
                schema = 'savings_sync_test_' + uuid4().hex
                await raw.execute(f'CREATE SCHEMA "{schema}"; SET search_path TO "{schema}"')
                sql = baseline_017((ROOT / 'database/000_init.sql').read_text(encoding='utf-8'))
                await raw.execute(sql.replace("set_config('finance_tracker.reset', 'on', true)", "set_config('finance_tracker.reset', 'off', true)"))
                user, saving = uuid4(), uuid4()
                await raw.execute("INSERT INTO users(id,google_sub,email,name,last_login_at) VALUES($1,'synthetic','synthetic@example.test','Synthetic',NOW())", user)
                await raw.execute("INSERT INTO savings(id,user_id,kind,name,opening_amount,start_date,notes) VALUES($1,$2,'CASH','Existing',1000,'2026-10-01','')", saving, user)
                await raw.execute("INSERT INTO saving_movements(id,saving_id,request_id,sequence,direction,amount,movement_date,notes) VALUES($1,$2,$3,1,'ADD',500,'2026-10-02','')", uuid4(), saving, uuid4())
            await raw.execute('BEGIN')
            tables = sorted(Base.metadata.tables)
            for table in tables:
                await raw.execute(f'LOCK TABLE {table} IN SHARE MODE')
            columns = {table: [r['column_name'] for r in await raw.fetch('SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=$1 ORDER BY ordinal_position', table)] for table in tables}
            before = {table: await raw.fetch(f'SELECT * FROM {table} ORDER BY 1,2') for table in tables}
            sql = (ROOT / 'database/018_savings_sync.sql').read_text(encoding='utf-8').replace('BEGIN;', '').replace('COMMIT;', '')
            await raw.execute(sql)
            after = {table: await raw.fetch('SELECT ' + ','.join('"' + col + '"' for col in columns[table]) + f' FROM {table} ORDER BY 1,2') for table in tables}
            assert before == after, 'Existing records changed'
            assert not await raw.fetchval('SELECT COUNT(*) FROM ledger_transactions WHERE saving_movement_id IS NOT NULL')
            assert not await raw.fetchval('SELECT COUNT(*) FROM routine_plans WHERE saving_id IS NOT NULL')
            await raw.execute('COMMIT')
            print('PASS: migration 018 preserves every existing record; no backfill/reset.')
        finally:
            await raw.execute('ROLLBACK')
            if schema:
                await raw.execute(f'SET search_path TO public; DROP SCHEMA "{schema}" CASCADE')
    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(check('--apply' in sys.argv))

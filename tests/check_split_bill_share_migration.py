"""Test 032 in a disposable synthetic schema only."""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from check_debt_installment_migration import engine, snapshot

async def check():
    schema = 'split_share_test_' + uuid4().hex
    async with engine.connect() as conn:
        db = (await conn.get_raw_connection()).driver_connection
        await db.execute(f'CREATE SCHEMA "{schema}"; SET search_path TO "{schema}"')
        try:
            baseline = (ROOT/'database/000_init.sql').read_text(encoding='utf-8')
            await db.execute(baseline)
            await db.execute('DROP TABLE split_bill_links')
            owner, group = uuid4(), uuid4()
            await db.execute("INSERT INTO users(id,google_sub,email,name,last_login_at) VALUES($1,'synthetic-share','synthetic@example.test','Synthetic',NOW())", owner)
            await db.execute("INSERT INTO split_bill_groups(id,user_id,name,start_date,end_date,version) VALUES($1,$2,'Synthetic group','2026-11-01','2026-11-30',1)", group, owner)
            tables = [r['tablename'] for r in await db.fetch('SELECT tablename FROM pg_tables WHERE schemaname=current_schema() ORDER BY tablename')]
            before = await snapshot(db, tables)
            sql = (ROOT/'database/032_split_bill_share_links.sql').read_text(encoding='utf-8')
            await db.execute(sql)
            await db.execute(sql)
            assert before == await snapshot(db, tables)
            assert await db.fetchval('SELECT COUNT(*) FROM split_bill_links') == 0
            await db.execute('INSERT INTO split_bill_links(group_id,token_hash) VALUES($1,$2)', group, 'a'*64)
            await db.execute(sql)
            assert await db.fetchval('SELECT token_hash FROM split_bill_links WHERE group_id=$1', group) == 'a'*64
            await db.execute('DELETE FROM split_bill_groups WHERE id=$1', group)
            assert await db.fetchval('SELECT COUNT(*) FROM split_bill_links') == 0
            print('PASS: migration 032 preserves rows, private default, repeat and cascading link deletion')
        finally:
            await db.execute('ROLLBACK')
            await db.execute('SET search_path TO public')
            await db.execute(f'DROP SCHEMA "{schema}" CASCADE')
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(check())

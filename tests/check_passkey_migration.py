"""Verify additive 021 on synthetic schema; --apply backs up every old record."""
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from check_debt_installment_migration import engine, snapshot

NEW = ('user_passkeys', 'passkey_challenges', 'passkey_recovery_codes')


async def check(apply=False):
    schema = None
    async with engine.connect() as conn:
        db = (await conn.get_raw_connection()).driver_connection
        try:
            if not apply:
                schema = 'passkey_test_' + uuid4().hex
                await db.execute(f'CREATE SCHEMA "{schema}"; SET search_path TO "{schema}"')
                baseline = (ROOT / 'database/000_init.sql').read_text(encoding='utf-8')
                await db.execute(baseline.replace("set_config('finance_tracker.reset', 'on', true)",
                                                 "set_config('finance_tracker.reset', 'off', true)"))
                await db.execute('DROP TABLE passkey_challenges, passkey_recovery_codes, user_passkeys; ALTER TABLE users DROP COLUMN auth_version')
                owner = uuid4()
                await db.execute("INSERT INTO users(id,google_sub,email,name,last_login_at) VALUES($1,'synthetic','synthetic@example.test','Synthetic',NOW())", owner)
                await db.execute("INSERT INTO debts(id,user_id,kind,person_name,principal,transaction_date,interest_type,interest_rate) VALUES($1,$2,'DEBT','Synthetic',1000,'2026-10-01','NONE',0)", uuid4(), owner)
            await db.execute('BEGIN')
            await db.execute("SET LOCAL lock_timeout = '10s'")
            tables = [row['tablename'] for row in await db.fetch('SELECT tablename FROM pg_tables WHERE schemaname=current_schema() ORDER BY tablename')]
            if any(table in tables for table in NEW):
                raise RuntimeError('021 already/partially applied; no changes made')
            for table in tables:
                await db.execute(f'LOCK TABLE "{table}" IN SHARE MODE')
            before = await snapshot(db, tables)
            if apply:
                directory = ROOT / '.migration-backups'
                directory.mkdir(exist_ok=True)
                stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
                (directory / f'passkey-021-{stamp}.json').write_text(json.dumps(before, default=str, ensure_ascii=False, indent=2), encoding='utf-8')
            sql = (ROOT / 'database/021_passkeys.sql').read_text(encoding='utf-8')
            await db.execute(sql.replace('BEGIN;', '').replace('COMMIT;', ''))
            after = await snapshot(db, tables)
            for user in after['users']:
                assert user.pop('auth_version') == 0
            assert before == after, 'Existing records changed'
            for table in NEW:
                assert await db.fetchval(f'SELECT count(*) FROM {table}') == 0
            await db.execute('COMMIT')
            print('PASS: 021 preserves all records; auth version 0 and three empty relational security tables.')
            if schema:
                from sqlalchemy.ext.asyncio import AsyncSession
                from app.models import User
                async with AsyncSession(bind=conn, expire_on_commit=False) as session:
                    assert (await session.get(User, owner)).auth_version == 0
                print('PASS: PostgreSQL ORM reads upgraded users; financial rows retained.')
        finally:
            await db.execute('ROLLBACK')
            if schema:
                await db.execute(f'SET search_path TO public; DROP SCHEMA "{schema}" CASCADE')
    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(check('--apply' in sys.argv))

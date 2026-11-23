"""Read-only release checks. Exit nonzero if the required schema cannot be verified."""
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.models import Base


def configured(*names):
    return all(bool(os.getenv(name, '').strip()) for name in names)


def report(label, ok):
    print(('PASS: ' if ok else 'PENDING: ') + label)


async def schema_issues(db: AsyncConnection) -> list[str]:
    """Check ORM schema coverage and the legacy constraint removed by migration 033."""
    columns = await db.execute(text("""
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
    """))
    actual: dict[str, set[str]] = {}
    for table_name, column_name in columns:
        actual.setdefault(table_name, set()).add(column_name)

    issues = []
    for table in sorted(Base.metadata.tables.values(), key=lambda table: table.name):
        if table.name not in actual:
            issues.append(f'Table missing or inaccessible: {table.name}')
            continue
        missing = sorted({column.name for column in table.columns} - actual[table.name])
        if missing:
            issues.append(f'Columns missing or inaccessible: {table.name} ({", ".join(missing)})')

    legacy_constraint = await db.scalar(text("""
        SELECT EXISTS (
            SELECT 1
            FROM pg_catalog.pg_constraint constraint_row
            JOIN pg_catalog.pg_class relation ON relation.oid = constraint_row.conrelid
            JOIN pg_catalog.pg_namespace namespace ON namespace.oid = relation.relnamespace
            WHERE namespace.nspname = current_schema()
              AND relation.relname = 'ledger_transactions'
              AND constraint_row.conname = 'ck_ledger_distinct_banks'
        )
    """))
    if legacy_constraint:
        issues.append('Legacy ledger constraint still present: run migration 033')
    return issues


async def check() -> int:
    load_dotenv(ROOT / '.env')
    from app.config.db_config import engine

    report('Payment gateway enabled', os.getenv('MIDTRANS_ENABLED', 'false').lower() == 'true')
    report('Merchant production environment', os.getenv('MIDTRANS_ENVIRONMENT') == 'production')
    report('Merchant credentials configured', configured('MIDTRANS_SERVER_KEY', 'MIDTRANS_WEBHOOK_TOKEN'))
    report('Recurring enabled', os.getenv('MIDTRANS_RECURRING_ENABLED', 'false').lower() == 'true')
    report('Separate backup encryption key configured', configured('BACKUP_ENCRYPTION_KEY'))
    local = engine.url.host in {'localhost', '127.0.0.1', '::1'}
    print('INFO: database scope is ' + ('local; hosted readiness unverified' if local else 'hosted'))
    report('Hosted database TLS configured', not local and os.getenv('DB_SSL', 'false').lower() in {'true', 'yes', '1'})

    try:
        async with engine.begin() as db:
            await db.execute(text('SET TRANSACTION READ ONLY'))
            issues = await schema_issues(db)
            if not issues:
                report('Required schema present', True)
                report('Database has an active admin', bool(await db.scalar(text(
                    'SELECT EXISTS (SELECT 1 FROM users WHERE admin_f=1 AND is_active=true)'
                ))))
    except (SQLAlchemyError, OSError) as error:
        print(f'FAIL: database checks could not run ({type(error).__name__})')
        return 1
    finally:
        await engine.dispose()

    if issues:
        for issue in issues:
            print('FAIL: ' + issue)
        print('Apply the pending migrations for this database before deploying.')
        return 1

    print('PENDING: verify public policies, merchant sandbox, hosted recovery, retention and support operationally.')
    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(check()))

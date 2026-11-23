"""Opt in to destructive maintenance only inside a disposable test schema."""
import re
from pathlib import Path

RESET_SQL = Path(__file__).resolve().parents[1] / 'database/reset_application_data.sql'


async def reset_synthetic_schema(db, schema: str):
    if not re.fullmatch(r'[a-z_]+_test_[0-9a-f]{32}', schema):
        raise ValueError('Reset tests require a randomly named synthetic schema')
    if await db.fetchval('SELECT current_schema()') != schema:
        raise ValueError('Reset test is connected to a different schema')
    target = await db.fetchval("SELECT current_database() || '.' || current_schema()")
    await db.fetchval("SELECT set_config('finance_tracker.confirm_reset', $1, false)", target)
    await db.execute(RESET_SQL.read_text(encoding='utf-8'))

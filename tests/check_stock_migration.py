"""Run 024 upgrades and competing purchases ONLY in a disposable schema."""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4
from datetime import date
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from check_debt_installment_migration import engine, snapshot
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User, StockNeed, StockProduct
from app.schemas.stock_schema import PurchaseInput
from app.services import stock_service
from fastapi import HTTPException


async def check():
    schema = 'stock_test_' + uuid4().hex
    async with engine.connect() as connection:
        db = (await connection.get_raw_connection()).driver_connection
        await db.execute(f'CREATE SCHEMA "{schema}"; SET search_path TO "{schema}"')
        try:
            baseline = (ROOT/'database/000_init.sql').read_text(encoding='utf-8')
            await db.execute(baseline.replace("set_config('finance_tracker.reset', 'on', true)", "set_config('finance_tracker.reset', 'off', true)"))
            await db.execute('DROP TABLE stock_events, stock_products, stock_needs')
            owner_id = uuid4()
            await db.execute("INSERT INTO users(id,google_sub,email,name,last_login_at) VALUES($1,'stock-synthetic','synthetic@example.test','Synthetic',NOW())", owner_id)
            await db.execute("INSERT INTO debts(id,user_id,kind,person_name,principal,transaction_date,interest_type,interest_rate) VALUES($1,$2,'DEBT','Synthetic',1000,'2026-10-01','NONE',0)", uuid4(), owner_id)
            tables = [r['tablename'] for r in await db.fetch('SELECT tablename FROM pg_tables WHERE schemaname=current_schema() ORDER BY tablename')]
            before = await snapshot(db, tables)
            upgrade = (ROOT/'database/024_stock_needs.sql').read_text(encoding='utf-8')
            await db.execute(upgrade)
            await db.execute(upgrade)
            assert before == await snapshot(db, tables)
            async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                need = StockNeed(user_id=owner_id, name='Synthetic', category='health', subcategory='vitamins', mode='monthly', next_review=date(2026,10,1))
                session.add(need); await session.flush()
                product = StockProduct(need_id=need.id, brand='Test', variant='30', package_unit='botol', package_size='30 tablet', preference='staple')
                session.add(product); await session.commit()
                need_id, product_id = need.id, product.id
            payloads = [PurchaseInput.model_validate({'RequestId': uuid4(), 'Version': 1, 'Quantity': 1, 'PurchaseDate': '2026-10-01', 'Amount': 50000, 'RecordExpense': True}) for _ in range(2)]
            async def buy(payload):
                async with engine.connect() as conn:
                    await conn.exec_driver_sql(f'SET search_path TO "{schema}"'); await conn.commit()
                    async with AsyncSession(bind=conn, expire_on_commit=False) as session:
                        user = await session.get(User, owner_id)
                        try:
                            await stock_service.purchase(need_id, product_id, payload, user, session)
                            return 201
                        except HTTPException as error:
                            await session.rollback()
                            return error.status_code
            results = await asyncio.gather(*(buy(payload) for payload in payloads))
            assert sorted(results) == [201,409], results
            assert await buy(payloads[results.index(201)]) == 201
            assert await db.fetchval('SELECT reserve_count FROM stock_products WHERE id=$1', product_id) == 1
            assert await db.fetchval('SELECT COUNT(*) FROM stock_events') == 1
            assert await db.fetchval('SELECT COUNT(*) FROM ledger_transactions') == 1
            populated = tables + ['stock_needs', 'stock_products', 'stock_events']
            existing = await snapshot(db, populated)
            await db.execute(upgrade)
            assert existing == await snapshot(db, populated)
            await db.execute('CREATE TABLE stock_sentinel(value INTEGER); INSERT INTO stock_sentinel VALUES(42)')
            await db.execute(baseline)
            for table in ('stock_needs','stock_products','stock_events'):
                assert await db.fetchval(f'SELECT COUNT(*) FROM {table}') == 0
            assert await db.fetchval('SELECT value FROM stock_sentinel') == 42
            print('PASS: 024 repeated upgrade preserves old/populated data; simultaneous purchases produce one stock change and one expense; retry is idempotent; baseline/reset succeeds only in synthetic schema.')
        finally:
            await db.execute('ROLLBACK; SET search_path TO public')
            await db.execute(f'DROP SCHEMA "{schema}" CASCADE')
    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(check())

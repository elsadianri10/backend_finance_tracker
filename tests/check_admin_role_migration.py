import asyncio,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from check_debt_installment_migration import engine,snapshot
from synthetic_database import reset_synthetic_schema
async def check():
    schema='admin_role_test_'+uuid4().hex
    async with engine.connect() as conn:
        db=(await conn.get_raw_connection()).driver_connection
        await db.execute(f'CREATE SCHEMA "{schema}"; SET search_path TO "{schema}"')
        try:
            baseline=(ROOT/'database/000_init.sql').read_text(encoding='utf-8');keep=baseline
            await db.execute(keep);await db.execute('DROP TABLE user_admin_audit; ALTER TABLE users DROP COLUMN admin_f')
            owner,other=uuid4(),uuid4()
            for user,email in [(owner,'elsadianri10@gmail.com'),(other,'synthetic@example.test')]:
                await db.execute("INSERT INTO users(id,google_sub,email,name,last_login_at) VALUES($1,$2,$3,'Synthetic',now())",user,str(user),email)
            await db.execute("INSERT INTO savings(id,user_id,kind,name,opening_amount,start_date,notes) VALUES($1,$2,'CASH','Synthetic preserved',1234567,'2026-11-01','')",uuid4(),owner)
            tables=[r['tablename'] for r in await db.fetch('SELECT tablename FROM pg_tables WHERE schemaname=current_schema() ORDER BY tablename')]
            before=await snapshot(db,tables);sql=(ROOT/'database/031_user_admin_roles.sql').read_text(encoding='utf-8');await db.execute(sql)
            after=await snapshot(db,tables)
            for row in after['users']:assert row.pop('admin_f')==(1 if row['id']==owner else 0)
            assert before==after
            await db.execute('UPDATE users SET admin_f=1 WHERE id=$1',other)
            all_tables=tables+['user_admin_audit'];expected=await snapshot(db,all_tables)
            await db.execute(sql);await db.execute(keep);assert expected==await snapshot(db,all_tables)
            await reset_synthetic_schema(db, schema);assert await db.fetchval('SELECT COUNT(*) FROM users')==0
            print('PASS: additive/repeated 031 preserves all old fields and finances; owner seeded, assigned admins preserved; reset only in synthetic schema.')
        finally:
            await db.execute('ROLLBACK');await db.execute('SET search_path TO public');await db.execute(f'DROP SCHEMA "{schema}" CASCADE')
    await engine.dispose()
if __name__=='__main__':asyncio.run(check())

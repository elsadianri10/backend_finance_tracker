BEGIN;
ALTER TABLE users ADD COLUMN IF NOT EXISTS admin_f SMALLINT NOT NULL DEFAULT 0;
DO $$ BEGIN
    IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='ck_user_admin_f' AND conrelid='users'::regclass) THEN
        ALTER TABLE users ADD CONSTRAINT ck_user_admin_f CHECK(admin_f IN (0,1));
    END IF;
END $$;
UPDATE users SET admin_f=1 WHERE lower(trim(email))='elsadianri10@gmail.com' AND admin_f<>1;
CREATE TABLE IF NOT EXISTS user_admin_audit (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
    previous_f SMALLINT NOT NULL,
    admin_f SMALLINT NOT NULL,
    reason VARCHAR(500) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_admin_audit_flags CHECK(previous_f IN (0,1) AND admin_f IN (0,1))
);
CREATE INDEX IF NOT EXISTS ix_admin_audit_user_created ON user_admin_audit(user_id,created_at);
COMMIT;

-- Initialize one 30-day trial per existing account, preserving payments and grants.
BEGIN;
ALTER TABLE account_access ADD COLUMN IF NOT EXISTS trial_started_at TIMESTAMPTZ;
ALTER TABLE account_access ADD COLUMN IF NOT EXISTS trial_until TIMESTAMPTZ;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'account_access'::regclass AND conname = 'ck_access_trial_dates') THEN
        ALTER TABLE account_access ADD CONSTRAINT ck_access_trial_dates CHECK (
            (trial_started_at IS NULL AND trial_until IS NULL) OR
            (trial_started_at IS NOT NULL AND trial_until IS NOT NULL AND trial_until > trial_started_at)
        );
    END IF;
END $$;
INSERT INTO account_access(user_id, trial_started_at, trial_until)
SELECT id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + INTERVAL '720 hours' FROM users
ON CONFLICT (user_id) DO UPDATE SET
    trial_started_at = EXCLUDED.trial_started_at,
    trial_until = EXCLUDED.trial_until,
    version = account_access.version + 1
WHERE account_access.trial_started_at IS NULL;
COMMIT;

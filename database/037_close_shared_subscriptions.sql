-- Keep existing groups active until their owner closes them.
BEGIN;

ALTER TABLE shared_subscriptions ADD COLUMN IF NOT EXISTS closed_on DATE;

COMMIT;

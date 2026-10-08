BEGIN;
ALTER TABLE billing_transactions ADD COLUMN transaction_date DATE;
-- Historical transaction dates are unknown; preserve existing schedules unchanged.
COMMIT;

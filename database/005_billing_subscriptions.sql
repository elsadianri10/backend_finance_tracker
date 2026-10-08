BEGIN;
ALTER TABLE billing_transactions ADD COLUMN transaction_kind VARCHAR(20) NOT NULL DEFAULT 'ONE_TIME';
UPDATE billing_transactions SET transaction_kind = 'INSTALLMENT' WHERE tenor > 0;
ALTER TABLE billing_transactions ALTER COLUMN last_installment DROP NOT NULL;
ALTER TABLE billing_transactions ADD COLUMN stopped_on DATE;
ALTER TABLE billing_transactions ADD COLUMN recurring_billing_day INTEGER;
ALTER TABLE billing_transactions ADD COLUMN recurring_due_day INTEGER;
ALTER TABLE billing_transactions ADD CONSTRAINT ck_billing_transaction_kind CHECK (
    (transaction_kind = 'ONE_TIME' AND tenor = 0 AND last_installment IS NOT NULL AND stopped_on IS NULL)
    OR (transaction_kind = 'INSTALLMENT' AND tenor > 0 AND last_installment IS NOT NULL AND stopped_on IS NULL)
    OR (transaction_kind = 'SUBSCRIPTION' AND tenor = 0 AND last_installment IS NULL)
);
ALTER TABLE billing_installments ADD COLUMN charged_on DATE;
DO $$
DECLARE old_check RECORD;
BEGIN
    FOR old_check IN SELECT conname FROM pg_constraint
        WHERE conrelid = 'billing_installments'::regclass AND contype = 'c'
          AND pg_get_constraintdef(oid) LIKE '%sequence%'
    LOOP
        EXECUTE format('ALTER TABLE billing_installments DROP CONSTRAINT %I', old_check.conname);
    END LOOP;
END $$;
ALTER TABLE billing_installments ADD CONSTRAINT ck_billing_installment_sequence CHECK (sequence >= 1);
COMMIT;

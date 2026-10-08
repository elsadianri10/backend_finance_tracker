-- Per-account monthly and payment administration fees. Existing accounts start at zero.
BEGIN;
ALTER TABLE billing_accounts
    ADD COLUMN monthly_fee NUMERIC(18,0) NOT NULL DEFAULT 0,
    ADD COLUMN payment_fee NUMERIC(18,0) NOT NULL DEFAULT 0,
    ADD CONSTRAINT ck_billing_account_fees CHECK (
        monthly_fee BETWEEN 0 AND 1000000000000 AND payment_fee BETWEEN 0 AND 1000000000000
    );
COMMIT;

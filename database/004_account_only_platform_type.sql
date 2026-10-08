-- Run after 003. PlatformType belongs only to individual billing accounts.
BEGIN;

ALTER TABLE billing_platforms DROP CONSTRAINT ck_billing_platform_type;
ALTER TABLE billing_platforms DROP COLUMN platform_type;

-- billing_accounts.platform_type retains NOT NULL and ck_billing_account_type:
-- only CREDIT_CARD and PAY_LATER are accepted.
COMMIT;

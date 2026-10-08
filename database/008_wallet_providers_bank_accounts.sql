-- Upgrade existing databases through 007. Keeps provider IDs and all billing data.
BEGIN;
ALTER TABLE billing_platforms RENAME TO wallet_providers;
ALTER TABLE wallet_providers ADD COLUMN bank_f INTEGER NOT NULL DEFAULT 0;
ALTER TABLE wallet_providers ADD CONSTRAINT ck_wallet_provider_bank_f CHECK (bank_f IN (0, 1));
UPDATE wallet_providers SET bank_f = 1 WHERE name IN ('BCA', 'BRI');

CREATE TABLE bank_accounts (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    platform_id INTEGER NOT NULL REFERENCES wallet_providers(id),
    account_number_encrypted TEXT NOT NULL,
    card_number_encrypted TEXT NOT NULL,
    valid_thru VARCHAR(7) NOT NULL,
    admin_fee NUMERIC(18, 0) NOT NULL DEFAULT 0,
    others_fee NUMERIC(18, 0) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_bank_account_fees CHECK (admin_fee BETWEEN 0 AND 1000000000000 AND others_fee BETWEEN 0 AND 1000000000000)
);
CREATE INDEX ix_bank_accounts_user_id ON bank_accounts(user_id);
COMMIT;

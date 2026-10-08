-- Run after 000_init.sql. Adds account setup only; no transactions yet.
BEGIN;

CREATE TABLE billing_platforms (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE billing_accounts (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    platform_id INTEGER NOT NULL,
    platform_type VARCHAR(20) NOT NULL,
    account_type VARCHAR(100),
    account_number_encrypted TEXT,
    valid_thru VARCHAR(7),
    has_fixed_bill_date BOOLEAN NOT NULL,
    billing_date INTEGER,
    due_date INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (platform_id, platform_type) REFERENCES billing_platform_types(platform_id, platform_type),
    CONSTRAINT ck_billing_account_type CHECK (platform_type IN ('CREDIT_CARD', 'PAY_LATER')),
    CONSTRAINT ck_billing_card_fields CHECK (
        (platform_type = 'CREDIT_CARD' AND account_type IS NOT NULL AND account_number_encrypted IS NOT NULL AND valid_thru IS NOT NULL)
        OR (platform_type = 'PAY_LATER' AND account_type IS NULL AND account_number_encrypted IS NULL AND valid_thru IS NULL)
    ),
    CONSTRAINT ck_billing_fixed_dates CHECK (
        (has_fixed_bill_date = TRUE AND billing_date IS NOT NULL AND due_date IS NOT NULL AND billing_date BETWEEN 1 AND 31 AND due_date BETWEEN 1 AND 31)
        OR (has_fixed_bill_date = FALSE AND billing_date IS NULL AND due_date IS NULL)
    )
);

CREATE INDEX ix_billing_accounts_user_id ON billing_accounts(user_id);

INSERT INTO billing_platforms (id, name) VALUES
    (1, 'BCA'), (2, 'BRI'), (3, 'GoPay Later'), (4, 'ShopeePay Later'), (5, 'Kredivo'), (6, 'CareNow');

COMMIT;

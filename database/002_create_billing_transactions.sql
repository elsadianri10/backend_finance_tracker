BEGIN;
CREATE TABLE billing_transactions (
    id UUID PRIMARY KEY,
    account_id UUID NOT NULL REFERENCES billing_accounts(id),
    description VARCHAR(255) NOT NULL,
    tenor INTEGER NOT NULL CHECK (tenor IN (0, 3, 6, 9, 12, 18, 24)),
    first_installment DATE NOT NULL,
    last_installment DATE NOT NULL,
    amount NUMERIC(18, 0) NOT NULL CHECK (amount > 0),
    notes VARCHAR(2000) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_billing_transactions_account ON billing_transactions(account_id);
CREATE TABLE billing_installments (
    id UUID PRIMARY KEY,
    transaction_id UUID NOT NULL REFERENCES billing_transactions(id),
    sequence INTEGER NOT NULL CHECK (sequence BETWEEN 1 AND 24),
    amount NUMERIC(18, 0) NOT NULL CHECK (amount > 0),
    due_date DATE NOT NULL,
    paid_at TIMESTAMPTZ,
    UNIQUE (transaction_id, sequence)
);
COMMIT;

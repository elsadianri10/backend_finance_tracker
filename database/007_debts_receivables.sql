-- Debts/receivables and dated partial payments. Existing data is retained.
BEGIN;

CREATE TABLE debts (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    kind VARCHAR(20) NOT NULL,
    person_name VARCHAR(255) NOT NULL,
    principal NUMERIC(18, 0) NOT NULL,
    transaction_date DATE NOT NULL,
    due_date DATE,
    interest_type VARCHAR(20) NOT NULL,
    interest_rate NUMERIC(5, 2) NOT NULL,
    notes VARCHAR(2000) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_debt_kind CHECK (kind IN ('DEBT', 'RECEIVABLE')),
    CONSTRAINT ck_debt_principal CHECK (principal > 0 AND principal <= 1000000000000),
    CONSTRAINT ck_debt_interest CHECK (
        (interest_type = 'NONE' AND interest_rate = 0)
        OR (interest_type = 'MONTHLY' AND interest_rate > 0 AND interest_rate <= 100)
    ),
    CONSTRAINT ck_debt_due_date CHECK (due_date IS NULL OR due_date >= transaction_date)
);
CREATE INDEX ix_debts_user_id ON debts(user_id);

CREATE TABLE debt_payments (
    id UUID PRIMARY KEY,
    debt_id UUID NOT NULL REFERENCES debts(id),
    request_id UUID NOT NULL,
    sequence INTEGER NOT NULL,
    amount NUMERIC(18, 0) NOT NULL,
    payment_date DATE NOT NULL,
    notes VARCHAR(2000) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (debt_id, request_id),
    UNIQUE (debt_id, sequence),
    CONSTRAINT ck_debt_payment_amount CHECK (amount > 0 AND amount <= 9007199254740991),
    CONSTRAINT ck_debt_payment_sequence CHECK (sequence >= 1)
);

COMMIT;

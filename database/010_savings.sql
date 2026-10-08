BEGIN;
CREATE TABLE savings (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    kind VARCHAR(20) NOT NULL,
    name VARCHAR(255) NOT NULL,
    opening_amount NUMERIC(18,3) NOT NULL,
    start_date DATE NOT NULL,
    bank_account_id UUID REFERENCES bank_accounts(id) ON DELETE SET NULL,
    bank_name VARCHAR(100),
    bank_account_masked VARCHAR(30),
    weight_per_piece NUMERIC(12,3),
    pieces INTEGER,
    purchase_cost NUMERIC(18,0),
    price_per_gram NUMERIC(18,0),
    maturity_date DATE,
    interest_rate NUMERIC(5,2),
    notes VARCHAR(2000) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_saving_kind CHECK (kind IN ('CASH','GOLD','DEPOSIT')),
    CONSTRAINT ck_saving_opening CHECK (opening_amount > 0)
);
CREATE INDEX ix_savings_user_id ON savings(user_id);
CREATE TABLE saving_movements (
    id UUID PRIMARY KEY,
    saving_id UUID NOT NULL REFERENCES savings(id),
    request_id UUID NOT NULL,
    sequence INTEGER NOT NULL,
    direction VARCHAR(10) NOT NULL,
    amount NUMERIC(18,3) NOT NULL,
    movement_date DATE NOT NULL,
    notes VARCHAR(2000) NOT NULL,
    UNIQUE (saving_id, request_id),
    UNIQUE (saving_id, sequence),
    CONSTRAINT ck_saving_movement CHECK (direction IN ('ADD','REMOVE') AND amount > 0)
);
COMMIT;

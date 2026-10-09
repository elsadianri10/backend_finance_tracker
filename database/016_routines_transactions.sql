-- Additive relational schema. No existing financial records are modified.
BEGIN;
CREATE TABLE routine_plans (
	id UUID NOT NULL,
	user_id UUID NOT NULL,
	kind VARCHAR(20) NOT NULL,
	recipient VARCHAR(120) NOT NULL,
	name VARCHAR(200) NOT NULL,
	amount BIGINT NOT NULL,
	status VARCHAR(12) NOT NULL,
	first_due_date DATE NOT NULL,
	interval_months INTEGER NOT NULL,
	total_cycles INTEGER NOT NULL,
	initial_paid INTEGER NOT NULL,
	destination_bank_id UUID,
	billing_transaction_id UUID,
	notes VARCHAR(2000) NOT NULL,
	version INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_routine_kind CHECK (kind IN ('SUBSCRIPTION','CONTRIBUTION','TRANSFER')),
	CONSTRAINT ck_routine_status CHECK (status IN ('ACTIVE','NOTE','STOPPED')),
	CONSTRAINT ck_routine_amount CHECK (amount BETWEEN 0 AND 1000000000000 AND (status <> 'ACTIVE' OR amount > 0)),
	CONSTRAINT ck_routine_interval CHECK (interval_months BETWEEN 1 AND 12),
	CONSTRAINT ck_routine_cycles CHECK (total_cycles BETWEEN 0 AND 60 AND initial_paid >= 0 AND (total_cycles = 0 OR initial_paid <= total_cycles)),
	CONSTRAINT ck_routine_version CHECK (version > 0),
	FOREIGN KEY(user_id) REFERENCES users (id),
	FOREIGN KEY(destination_bank_id) REFERENCES bank_accounts (id) ON DELETE SET NULL,
	FOREIGN KEY(billing_transaction_id) REFERENCES billing_transactions (id) ON DELETE SET NULL
);

CREATE INDEX ix_routine_owner ON routine_plans (user_id);

CREATE TABLE routine_payments (
	id UUID NOT NULL,
	plan_id UUID NOT NULL,
	request_id UUID NOT NULL,
	sequence INTEGER NOT NULL,
	due_date DATE NOT NULL,
	voided_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	CONSTRAINT uq_routine_payment_request UNIQUE (plan_id, request_id),
	CONSTRAINT ck_routine_payment_sequence CHECK (sequence > 0),
	FOREIGN KEY(plan_id) REFERENCES routine_plans (id)
);

CREATE UNIQUE INDEX uq_routine_payment_sequence ON routine_payments (plan_id, sequence) WHERE voided_at IS NULL;

CREATE TABLE ledger_transactions (
	id UUID NOT NULL,
	user_id UUID NOT NULL,
	kind VARCHAR(10) NOT NULL,
	category VARCHAR(20) NOT NULL,
	description VARCHAR(323) NOT NULL,
	amount BIGINT NOT NULL,
	transaction_date DATE NOT NULL,
	source_bank_id UUID,
	destination_bank_id UUID,
	source_label VARCHAR(150) NOT NULL,
	destination_label VARCHAR(150) NOT NULL,
	notes VARCHAR(2000) NOT NULL,
	routine_payment_id UUID,
	billing_installment_id UUID,
	legacy_id VARCHAR(200),
	voided_at TIMESTAMP WITH TIME ZONE,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_ledger_legacy UNIQUE (user_id, legacy_id),
	CONSTRAINT ck_ledger_kind CHECK (kind IN ('income','expense','transfer')),
	CONSTRAINT ck_ledger_amount CHECK (amount > 0 AND amount <= 1000000000000),
	CONSTRAINT ck_ledger_distinct_banks CHECK (source_bank_id IS NULL OR destination_bank_id IS NULL OR source_bank_id <> destination_bank_id),
	FOREIGN KEY(user_id) REFERENCES users (id),
	FOREIGN KEY(source_bank_id) REFERENCES bank_accounts (id) ON DELETE SET NULL,
	FOREIGN KEY(destination_bank_id) REFERENCES bank_accounts (id) ON DELETE SET NULL,
	UNIQUE (routine_payment_id),
	FOREIGN KEY(routine_payment_id) REFERENCES routine_payments (id),
	FOREIGN KEY(billing_installment_id) REFERENCES billing_installments (id) ON DELETE SET NULL
);

CREATE INDEX ix_ledger_owner_date ON ledger_transactions (user_id, transaction_date);

CREATE UNIQUE INDEX uq_ledger_billing_installment ON ledger_transactions (billing_installment_id) WHERE voided_at IS NULL;

CREATE TABLE transaction_imports (
	user_id UUID NOT NULL,
	imported_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (user_id),
	FOREIGN KEY(user_id) REFERENCES users (id)
);
COMMIT;

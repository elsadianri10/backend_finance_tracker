-- Additive subscription billing tables. No financial rows are modified.
BEGIN;

CREATE TABLE IF NOT EXISTS subscription_orders (
	id UUID NOT NULL,
	user_id UUID NOT NULL,
	request_id UUID NOT NULL,
	plan VARCHAR(10) NOT NULL,
	amount INTEGER NOT NULL,
	environment VARCHAR(10) NOT NULL,
	auto_renew BOOLEAN NOT NULL,
	consented_at TIMESTAMP WITH TIME ZONE,
	consent_version VARCHAR(30),
	state VARCHAR(12) DEFAULT 'PENDING' NOT NULL,
	redirect_url VARCHAR(2048),
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	access_before TIMESTAMP WITH TIME ZONE,
	renewal_state VARCHAR(12) DEFAULT 'NONE' NOT NULL,
	provider_subscription_id VARCHAR(100),
	next_charge_at TIMESTAMP WITH TIME ZONE,
	setup_attempted_at TIMESTAMP WITH TIME ZONE,
	cancel_requested_at TIMESTAMP WITH TIME ZONE,
	cancelled_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	CONSTRAINT uq_subscription_request UNIQUE (user_id, request_id),
	CONSTRAINT ck_subscription_plan CHECK (plan IN ('MONTHLY','ANNUAL')),
	CONSTRAINT ck_subscription_environment CHECK (environment IN ('sandbox','production')),
	CONSTRAINT ck_subscription_amount CHECK (amount > 0),
	CONSTRAINT ck_subscription_state CHECK (state IN ('PENDING','PAID','EXPIRED','CANCELLED','DENIED','REFUNDED','REVIEW')),
	CONSTRAINT ck_subscription_renewal CHECK (renewal_state IN ('NONE','PENDING','CREATING','ACTIVE','REVIEW','CANCELLED','FAILED')),
	CONSTRAINT ck_subscription_consent CHECK ((NOT auto_renew) OR (consented_at IS NOT NULL AND consent_version IS NOT NULL)),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE RESTRICT,
	UNIQUE (provider_subscription_id)
);

CREATE INDEX IF NOT EXISTS ix_subscription_user_created ON subscription_orders (user_id, created_at);

CREATE TABLE IF NOT EXISTS subscription_payments (
	id UUID NOT NULL,
	order_id UUID NOT NULL,
	transaction_id VARCHAR(100) NOT NULL,
	provider_order_id VARCHAR(100) NOT NULL,
	environment VARCHAR(10) NOT NULL,
	amount INTEGER NOT NULL,
	state VARCHAR(10) NOT NULL,
	paid_at TIMESTAMP WITH TIME ZONE NOT NULL,
	period_start TIMESTAMP WITH TIME ZONE NOT NULL,
	period_end TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_subscription_transaction UNIQUE (environment, transaction_id),
	CONSTRAINT uq_subscription_payment_order UNIQUE (environment, provider_order_id),
	CONSTRAINT ck_subscription_payment_state CHECK (state IN ('PAID','REFUNDED')),
	CONSTRAINT ck_subscription_payment_amount CHECK (amount > 0),
	FOREIGN KEY(order_id) REFERENCES subscription_orders (id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS ix_subscription_payment_order ON subscription_payments (order_id);

COMMIT;

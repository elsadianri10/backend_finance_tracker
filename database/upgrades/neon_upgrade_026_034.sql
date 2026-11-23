-- Neon upgrade from migration 025 through 034.
-- Run this entire file on the branch, database, and schema used by the backend.
-- Apply any missing migrations through 025 first. This file contains no reset.
-- Migration 027 starts a 30-day trial for existing users without one.
-- Migration 031 assigns admin_f=1 to the original admin account.
BEGIN;

-- Source: 026_account_access.sql
-- Additive account access and audit; no financial rows changed.
CREATE TABLE IF NOT EXISTS account_access (
	user_id UUID NOT NULL,
	subscription_plan VARCHAR(10) DEFAULT 'FREE' NOT NULL,
	subscription_until TIMESTAMP WITH TIME ZONE,
	complimentary BOOLEAN DEFAULT 'false' NOT NULL,
	complimentary_until TIMESTAMP WITH TIME ZONE,
	version INTEGER DEFAULT '1' NOT NULL,
	PRIMARY KEY (user_id),
	CONSTRAINT ck_access_plan CHECK (subscription_plan IN ('FREE','PRO')),
	CONSTRAINT ck_access_version CHECK (version > 0),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS access_audit (
	id UUID NOT NULL,
	user_id UUID NOT NULL,
	actor_id UUID,
	action VARCHAR(10) NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE,
	reason VARCHAR(500) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_access_audit_action CHECK (action IN ('GRANT','REVOKE')),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
	FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_access_audit_target ON access_audit (user_id, created_at);

-- Source: 027_account_trial.sql
-- Initialize one 30-day trial per existing account, preserving payments and grants.
ALTER TABLE account_access ADD COLUMN IF NOT EXISTS trial_started_at TIMESTAMPTZ;
ALTER TABLE account_access ADD COLUMN IF NOT EXISTS trial_until TIMESTAMPTZ;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'account_access'::regclass AND conname = 'ck_access_trial_dates') THEN
        ALTER TABLE account_access ADD CONSTRAINT ck_access_trial_dates CHECK (
            (trial_started_at IS NULL AND trial_until IS NULL) OR
            (trial_started_at IS NOT NULL AND trial_until IS NOT NULL AND trial_until > trial_started_at)
        );
    END IF;
END $$;
INSERT INTO account_access(user_id, trial_started_at, trial_until)
SELECT id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + INTERVAL '720 hours' FROM users
ON CONFLICT (user_id) DO UPDATE SET
    trial_started_at = EXCLUDED.trial_started_at,
    trial_until = EXCLUDED.trial_until,
    version = account_access.version + 1
WHERE account_access.trial_started_at IS NULL;

-- Source: 028_subscriptions.sql
-- Additive subscription billing tables. No financial rows are modified.

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

-- Source: 029_plan_archives.sql
-- Additive and reversible archive flags; balances, movements and financial links are preserved.
ALTER TABLE bank_accounts ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE savings ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT false;

-- Source: 030_account_deletions.sql
CREATE TABLE IF NOT EXISTS account_deletions (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    subject_id UUID NOT NULL,
    status VARCHAR(12) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT ck_deletion_status CHECK (status IN ('PENDING','REVIEWING','CANCELLED','CLEANUP','COMPLETED'))
);
CREATE INDEX IF NOT EXISTS ix_deletion_status_created ON account_deletions(status,created_at);
CREATE TABLE IF NOT EXISTS account_deletion_blobs (
    id UUID PRIMARY KEY,
    request_id UUID NOT NULL REFERENCES account_deletions(id) ON DELETE CASCADE,
    url VARCHAR(2048) NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_account_deletion_blobs_request_id ON account_deletion_blobs(request_id);

-- Source: 031_user_admin_roles.sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS admin_f SMALLINT NOT NULL DEFAULT 0;
DO $$ BEGIN
    IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='ck_user_admin_f' AND conrelid='users'::regclass) THEN
        ALTER TABLE users ADD CONSTRAINT ck_user_admin_f CHECK(admin_f IN (0,1));
    END IF;
END $$;
UPDATE users SET admin_f=1 WHERE lower(trim(email))='elsadianri10@gmail.com' AND admin_f<>1;
CREATE TABLE IF NOT EXISTS user_admin_audit (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
    previous_f SMALLINT NOT NULL,
    admin_f SMALLINT NOT NULL,
    reason VARCHAR(500) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_admin_audit_flags CHECK(previous_f IN (0,1) AND admin_f IN (0,1))
);
CREATE INDEX IF NOT EXISTS ix_admin_audit_user_created ON user_admin_audit(user_id,created_at);

-- Source: 032_split_bill_share_links.sql
-- Additive Split Bill share links. Existing groups remain private.
CREATE TABLE IF NOT EXISTS split_bill_links (
    group_id UUID PRIMARY KEY REFERENCES split_bill_groups(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Source: 033_allow_same_account_transfers.sql
-- Permit internal allocations within the same owned bank account.
-- Existing transactions, balances and payment links are preserved.
ALTER TABLE ledger_transactions DROP CONSTRAINT IF EXISTS ck_ledger_distinct_banks;

-- Source: 034_transaction_versions_wishlist_cleanup.sql
-- Preserve transactions and photo references while enabling edits and durable cleanup.
ALTER TABLE ledger_transactions ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1
    CONSTRAINT ck_ledger_version CHECK (version > 0);

CREATE TABLE IF NOT EXISTS wishlist_blob_cleanup (
    id UUID PRIMARY KEY,
    url VARCHAR(2048) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_attempt_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_wishlist_cleanup_attempt ON wishlist_blob_cleanup (last_attempt_at, created_at);

COMMIT;

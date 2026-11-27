-- Private subscription checklists, membership history, and links to existing income entries.
BEGIN;

CREATE TABLE IF NOT EXISTS shared_subscriptions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(150) NOT NULL,
    monthly_amount BIGINT NOT NULL,
    CONSTRAINT ck_shared_subscription_amount CHECK (monthly_amount BETWEEN 1 AND 1000000000)
);
CREATE INDEX IF NOT EXISTS ix_shared_subscriptions_owner ON shared_subscriptions (user_id);

CREATE TABLE IF NOT EXISTS shared_subscription_members (
    id UUID PRIMARY KEY,
    subscription_id UUID NOT NULL REFERENCES shared_subscriptions(id) ON DELETE CASCADE,
    name VARCHAR(150) NOT NULL,
    joined_on DATE NOT NULL,
    left_on DATE,
    pay_at_year_end BOOLEAN NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT ck_shared_member_dates CHECK (left_on IS NULL OR left_on >= joined_on),
    CONSTRAINT ck_shared_member_version CHECK (version > 0)
);
CREATE INDEX IF NOT EXISTS ix_shared_subscription_members_group ON shared_subscription_members (subscription_id);

CREATE TABLE IF NOT EXISTS shared_subscription_waivers (
    member_id UUID NOT NULL REFERENCES shared_subscription_members(id) ON DELETE CASCADE,
    month DATE NOT NULL,
    PRIMARY KEY (member_id, month)
);

CREATE TABLE IF NOT EXISTS shared_subscription_receipts (
    id UUID PRIMARY KEY,
    member_id UUID NOT NULL REFERENCES shared_subscription_members(id) ON DELETE CASCADE,
    transaction_id UUID UNIQUE REFERENCES ledger_transactions(id) ON DELETE CASCADE,
    amount BIGINT NOT NULL,
    paid_on DATE NOT NULL,
    start_month DATE,
    notes VARCHAR(1000) NOT NULL,
    CONSTRAINT ck_shared_receipt_amount CHECK (amount BETWEEN 1 AND 1000000000000)
);
CREATE INDEX IF NOT EXISTS ix_shared_subscription_receipts_member ON shared_subscription_receipts (member_id);

COMMIT;

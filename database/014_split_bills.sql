BEGIN;
CREATE TABLE split_bill_groups (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    document JSONB NOT NULL,
    version INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_split_bill_version CHECK (version > 0)
);
CREATE INDEX ix_split_bill_groups_user_id ON split_bill_groups(user_id);
COMMIT;

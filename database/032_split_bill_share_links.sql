-- Additive Split Bill share links. Existing groups remain private.
BEGIN;
CREATE TABLE IF NOT EXISTS split_bill_links (
    group_id UUID PRIMARY KEY REFERENCES split_bill_groups(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMIT;

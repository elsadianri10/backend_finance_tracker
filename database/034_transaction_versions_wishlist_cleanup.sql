-- Preserve transactions and photo references while enabling edits and durable cleanup.
BEGIN;
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

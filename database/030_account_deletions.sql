BEGIN;
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
COMMIT;

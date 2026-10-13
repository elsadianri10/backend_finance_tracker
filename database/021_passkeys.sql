-- Additive security migration. Existing users/data/sessions remain unchanged.
BEGIN;
ALTER TABLE users ADD COLUMN auth_version BIGINT NOT NULL DEFAULT 0;
ALTER TABLE users ADD CONSTRAINT ck_user_auth_version CHECK (auth_version >= 0);
CREATE TABLE user_passkeys (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    credential_id BYTEA NOT NULL UNIQUE,
    public_key BYTEA NOT NULL,
    name VARCHAR(80) NOT NULL,
    rp_id VARCHAR(253) NOT NULL,
    sign_count BIGINT NOT NULL,
    backed_up BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ,
    CONSTRAINT ck_passkey_counter CHECK (sign_count >= 0)
);
CREATE INDEX ix_passkeys_user_id ON user_passkeys(user_id);
CREATE TABLE passkey_challenges (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose VARCHAR(10) NOT NULL,
    challenge BYTEA NOT NULL,
    auth_version BIGINT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    attempts INTEGER NOT NULL,
    CONSTRAINT ck_passkey_purpose CHECK (purpose IN ('LOGIN','REGISTER','MANAGE')),
    CONSTRAINT ck_passkey_attempts CHECK (attempts BETWEEN 0 AND 5)
);
CREATE INDEX ix_passkey_challenges_user ON passkey_challenges(user_id);
CREATE TABLE passkey_recovery_codes (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code_hash VARCHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    used_at TIMESTAMPTZ
);
CREATE INDEX ix_recovery_user ON passkey_recovery_codes(user_id);
COMMIT;

-- Additive account access and audit; no financial rows changed.
BEGIN;
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
COMMIT;

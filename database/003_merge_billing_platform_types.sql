-- Run after 002. Existing platform restrictions are preserved.
-- NULL permits either account type; the account's own type remains required.
BEGIN;

ALTER TABLE billing_platforms ADD COLUMN platform_type VARCHAR(20);
ALTER TABLE billing_platforms ADD CONSTRAINT ck_billing_platform_type
    CHECK (platform_type IN ('CREDIT_CARD', 'PAY_LATER'));

UPDATE billing_platforms p SET platform_type = types.platform_type
FROM (
    SELECT platform_id, CASE WHEN COUNT(*) = 1 THEN MIN(platform_type) ELSE NULL END AS platform_type
    FROM billing_platform_types GROUP BY platform_id
) types WHERE p.id = types.platform_id;

-- Remove only the obsolete account foreign key, regardless of its generated name.
DO $$
DECLARE old_fk RECORD;
BEGIN
    FOR old_fk IN SELECT conname FROM pg_constraint
        WHERE conrelid = 'billing_accounts'::regclass
          AND confrelid = 'billing_platform_types'::regclass AND contype = 'f'
    LOOP
        EXECUTE format('ALTER TABLE billing_accounts DROP CONSTRAINT %I', old_fk.conname);
    END LOOP;
END $$;
ALTER TABLE billing_accounts ADD CONSTRAINT fk_billing_account_platform
    FOREIGN KEY (platform_id) REFERENCES billing_platforms(id);
DROP TABLE billing_platform_types;

COMMIT;

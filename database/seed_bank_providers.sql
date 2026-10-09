-- Bank names only; no account numbers or financial records.
-- Run against an existing schema with wallet_providers (migration 008+).
-- Existing providers and IDs are preserved; repeated runs do not add duplicates.
BEGIN;

LOCK TABLE wallet_providers IN EXCLUSIVE MODE;

WITH banks (name, existing_alias) AS (
    VALUES
        ('Bank Rakyat Indonesia (BRI)', 'BRI'),
        ('Bank Mandiri', 'Mandiri'),
        ('Bank Negara Indonesia (BNI)', 'BNI'),
        ('Bank Tabungan Negara (BTN)', 'BTN'),
        ('Bank Central Asia (BCA)', 'BCA'),
        ('Bank CIMB Niaga', 'CIMB Niaga'),
        ('Bank Danamon', 'Danamon'),
        ('Bank Permata', 'Permata'),
        ('Bank OCBC NISP', 'OCBC NISP'),
        ('Bank Maybank Indonesia', 'Maybank Indonesia'),
        ('Bank Panin', 'Panin'),
        ('Bank Mega', 'Mega'),
        ('Bank Jago', 'Jago'),
        ('Blu by BCA Digital', 'BLU'),
        ('SeaBank Indonesia', 'SeaBank'),
        ('Allo Bank', 'Allo Bank'),
        ('Bank Neo Commerce (BNC)', 'BNC'),
        ('Jenius (Bank BTPN)', 'Jenius'),
        ('Superbank', 'Superbank'),
        ('Bank Syariah Indonesia (BSI)', 'BSI'),
        ('BCA Syariah', 'BCA Syariah'),
        ('Bank Muamalat Indonesia', 'Muamalat'),
        ('Bank Mega Syariah', 'Mega Syariah'),
        ('Bank BTPN Syariah', 'BTPN Syariah'),
        ('Bank DKI (Jakarta)', 'Bank DKI'),
        ('Bank Jabar Banten (BJB)', 'BJB'),
        ('Bank Jateng', 'Bank Jateng'),
        ('Bank Jatim', 'Bank Jatim'),
        ('Bank Sumut', 'Bank Sumut'),
        ('HSBC Indonesia', 'HSBC'),
        ('Standard Chartered Bank', 'Standard Chartered'),
        ('Bank of China', 'Bank of China'),
        ('Deutsche Bank', 'Deutsche Bank'),
        ('UOB Indonesia', 'UOB')
), missing AS (
    SELECT b.name
    FROM banks b
    WHERE NOT EXISTS (
        SELECT 1 FROM wallet_providers p
        WHERE lower(trim(p.name)) IN (lower(b.name), lower(b.existing_alias))
    )
), next_ids AS (
    SELECT COALESCE(MAX(id), 0) AS last_id FROM wallet_providers
)
INSERT INTO wallet_providers (id, name, bank_f)
SELECT (next_ids.last_id + ROW_NUMBER() OVER (ORDER BY missing.name))::INTEGER,
       missing.name,
       1
FROM missing CROSS JOIN next_ids;

COMMIT;

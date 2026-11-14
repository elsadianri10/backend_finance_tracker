-- Additive and reversible archive flags; balances, movements and financial links are preserved.
BEGIN;
ALTER TABLE bank_accounts ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE savings ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT false;
COMMIT;

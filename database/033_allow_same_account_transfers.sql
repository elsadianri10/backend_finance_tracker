-- Permit internal allocations within the same owned bank account.
-- Existing transactions, balances and payment links are preserved.
BEGIN;
ALTER TABLE ledger_transactions DROP CONSTRAINT IF EXISTS ck_ledger_distinct_banks;
COMMIT;

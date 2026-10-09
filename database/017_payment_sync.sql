-- Additive payment links; historical payments are not backfilled automatically.
BEGIN;
ALTER TABLE routine_plans ADD COLUMN debt_id UUID REFERENCES debts(id) ON DELETE SET NULL;
ALTER TABLE ledger_transactions ADD COLUMN debt_payment_id UUID REFERENCES debt_payments(id) ON DELETE SET NULL;
ALTER TABLE ledger_transactions ADD COLUMN request_id UUID;
ALTER TABLE ledger_transactions ADD COLUMN request_hash VARCHAR(64);
ALTER TABLE ledger_transactions ADD CONSTRAINT uq_ledger_debt_payment UNIQUE(debt_payment_id);
ALTER TABLE ledger_transactions ADD CONSTRAINT uq_ledger_request UNIQUE(user_id, request_id);
COMMIT;

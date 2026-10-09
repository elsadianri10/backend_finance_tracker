-- Additive links only. Existing savings and transaction balances are preserved.
BEGIN;
ALTER TABLE routine_plans ADD COLUMN saving_id UUID REFERENCES savings(id);
ALTER TABLE ledger_transactions ADD COLUMN saving_movement_id UUID REFERENCES saving_movements(id);
ALTER TABLE ledger_transactions ADD CONSTRAINT uq_ledger_saving_movement UNIQUE (saving_movement_id);
COMMIT;

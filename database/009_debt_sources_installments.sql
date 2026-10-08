BEGIN;
ALTER TABLE debts ADD COLUMN source_bank_account_id UUID REFERENCES bank_accounts(id) ON DELETE SET NULL;
ALTER TABLE debts ADD COLUMN source_bank_name VARCHAR(100);
ALTER TABLE debts ADD COLUMN source_account_number_masked VARCHAR(30);
ALTER TABLE debts ADD COLUMN installment_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE debts ADD COLUMN installment_amounts JSON NOT NULL DEFAULT '[]';
ALTER TABLE debts ADD CONSTRAINT ck_debt_installments CHECK (installment_count BETWEEN 0 AND 60 AND (installment_count = 0 OR due_date IS NOT NULL));
COMMIT;

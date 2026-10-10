-- Preserve debt terms, payment history, and installment order; never reset data.
BEGIN;
LOCK TABLE debts IN ACCESS EXCLUSIVE MODE;

CREATE TABLE debt_installments (
    debt_id UUID NOT NULL REFERENCES debts(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    amount NUMERIC(18, 0) NOT NULL,
    PRIMARY KEY (debt_id, sequence),
    CONSTRAINT ck_debt_installment_sequence CHECK (sequence BETWEEN 1 AND 60),
    CONSTRAINT ck_debt_installment_amount CHECK (amount > 0 AND amount <= 1000000000000)
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM debts WHERE json_typeof(installment_amounts) IS DISTINCT FROM 'array') THEN
        RAISE EXCEPTION 'Invalid legacy installment array; migration cancelled';
    END IF;
    IF EXISTS (SELECT 1 FROM debts WHERE json_array_length(installment_amounts) <> installment_count) THEN
        RAISE EXCEPTION 'Installment count differs from legacy amounts; migration cancelled';
    END IF;
    IF EXISTS (
        SELECT 1 FROM debts d CROSS JOIN LATERAL json_array_elements(d.installment_amounts) v
        WHERE json_typeof(v) <> 'number' OR v::text !~ '^[0-9]+$'
    ) THEN
        RAISE EXCEPTION 'Legacy amounts must be whole rupiah; migration cancelled';
    END IF;
END $$;

INSERT INTO debt_installments (debt_id, sequence, amount)
SELECT d.id, v.sequence::integer, v.amount::text::numeric
FROM debts d CROSS JOIN LATERAL json_array_elements(d.installment_amounts)
    WITH ORDINALITY AS v(amount, sequence);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM debts d WHERE d.installment_count > 0
        AND d.principal <> (SELECT sum(i.amount) FROM debt_installments i WHERE i.debt_id = d.id)
    ) THEN
        RAISE EXCEPTION 'Installment total differs from principal; migration cancelled';
    END IF;
    IF EXISTS (
        SELECT 1 FROM debts d WHERE d.installment_amounts::jsonb <> COALESCE(
            (SELECT jsonb_agg(i.amount ORDER BY i.sequence) FROM debt_installments i WHERE i.debt_id = d.id), '[]'::jsonb)
    ) THEN
        RAISE EXCEPTION 'Installment backfill differs from original; migration cancelled';
    END IF;
END $$;

ALTER TABLE debts DROP COLUMN installment_amounts;
COMMIT;

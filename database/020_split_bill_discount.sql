-- Add a typed nominal discount; existing expenses retain identical totals.
BEGIN;
ALTER TABLE split_bill_expenses ADD COLUMN discount BIGINT NOT NULL DEFAULT 0;
ALTER TABLE split_bill_expenses ADD CONSTRAINT ck_split_discount
    CHECK (discount BETWEEN 0 AND 1000000000000);
COMMIT;

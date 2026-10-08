BEGIN;
ALTER TABLE savings ADD COLUMN metal_type VARCHAR(10);
UPDATE savings SET metal_type = 'GOLD' WHERE kind = 'GOLD';
ALTER TABLE savings ADD CONSTRAINT ck_saving_metal_type CHECK (
    (kind = 'GOLD' AND metal_type IS NOT NULL AND metal_type IN ('GOLD','SILVER'))
    OR (kind <> 'GOLD' AND metal_type IS NULL)
);
COMMIT;

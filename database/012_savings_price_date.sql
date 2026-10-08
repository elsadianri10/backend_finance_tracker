-- Record the date of a manually entered gold/silver price.
-- Existing prices keep NULL: their historical price date is unknown.
BEGIN;
ALTER TABLE savings ADD COLUMN price_date DATE;
COMMIT;

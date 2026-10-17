-- Additive migration. Existing URL photos and financial records remain unchanged.
BEGIN;
ALTER TABLE wishlist_photos ADD COLUMN IF NOT EXISTS blob_url VARCHAR(2048);
COMMIT;

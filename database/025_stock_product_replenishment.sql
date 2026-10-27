-- Product-specific reminder overrides. Existing stock and history stay unchanged.
BEGIN;
ALTER TABLE stock_products ADD COLUMN IF NOT EXISTS replenishment_paused BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE stock_products ADD COLUMN IF NOT EXISTS replenishment_snoozed_until DATE;
COMMIT;

-- Add private, user-owned budget plans, categories, and line items.
BEGIN;

CREATE TABLE IF NOT EXISTS budgets (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(150) NOT NULL,
    months INTEGER,
    version INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT ck_budget_months CHECK (months BETWEEN 1 AND 120),
    CONSTRAINT ck_budget_version CHECK (version > 0)
);
CREATE INDEX IF NOT EXISTS ix_budgets_user_id ON budgets (user_id);

CREATE TABLE IF NOT EXISTS budget_categories (
    id UUID PRIMARY KEY,
    budget_id UUID NOT NULL REFERENCES budgets(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    name VARCHAR(100) NOT NULL,
    notes VARCHAR(1000) NOT NULL,
    CONSTRAINT uq_budget_category_position UNIQUE (budget_id, position)
);

CREATE TABLE IF NOT EXISTS budget_items (
    id UUID PRIMARY KEY,
    category_id UUID NOT NULL REFERENCES budget_categories(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    name VARCHAR(200) NOT NULL,
    brand VARCHAR(100) NOT NULL,
    seller VARCHAR(150) NOT NULL,
    specification VARCHAR(150) NOT NULL,
    unit_price BIGINT NOT NULL,
    quantity INTEGER NOT NULL,
    link VARCHAR(2048) NOT NULL,
    notes VARCHAR(1000) NOT NULL,
    CONSTRAINT uq_budget_item_position UNIQUE (category_id, position),
    CONSTRAINT ck_budget_item_quantity CHECK (quantity BETWEEN 1 AND 10000),
    CONSTRAINT ck_budget_item_price CHECK (unit_price BETWEEN 0 AND 1000000000)
);

COMMIT;

-- Additive only. No existing financial or Wishlist records are modified.
BEGIN;
CREATE TABLE IF NOT EXISTS stock_needs (
	id UUID NOT NULL,
	user_id UUID NOT NULL,
	name VARCHAR(150) NOT NULL,
	category VARCHAR(20) NOT NULL,
	subcategory VARCHAR(60) NOT NULL,
	mode VARCHAR(20) NOT NULL,
	reserve_threshold INTEGER NOT NULL,
	next_review DATE,
	snoozed_until DATE,
	paused BOOLEAN NOT NULL,
	archived BOOLEAN NOT NULL,
	buy_requested BOOLEAN NOT NULL,
	notes VARCHAR(2000) NOT NULL,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_stock_category CHECK (category IN ('health','consumption','beauty')),
	CONSTRAINT ck_stock_mode CHECK (mode IN ('monthly','low_stock','manual')),
	CONSTRAINT ck_stock_need_limits CHECK (reserve_threshold BETWEEN 0 AND 10000 AND version > 0),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_stock_need_owner ON stock_needs (user_id);

CREATE TABLE IF NOT EXISTS stock_products (
	id UUID NOT NULL,
	need_id UUID NOT NULL,
	brand VARCHAR(150) NOT NULL,
	variant VARCHAR(150) NOT NULL,
	package_unit VARCHAR(40) NOT NULL,
	package_size VARCHAR(100) NOT NULL,
	preference VARCHAR(10) NOT NULL,
	active_count INTEGER NOT NULL,
	reserve_count INTEGER NOT NULL,
	near_empty BOOLEAN NOT NULL,
	opened_on DATE,
	archived BOOLEAN NOT NULL,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_stock_preference CHECK (preference IN ('staple','trial')),
	CONSTRAINT ck_stock_counts CHECK (active_count BETWEEN 0 AND 10000 AND reserve_count BETWEEN 0 AND 10000 AND version > 0),
	FOREIGN KEY(need_id) REFERENCES stock_needs (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_stock_product_need ON stock_products (need_id);

CREATE TABLE IF NOT EXISTS stock_events (
	id UUID NOT NULL,
	user_id UUID NOT NULL,
	product_id UUID NOT NULL,
	kind VARCHAR(10) NOT NULL,
	event_date DATE NOT NULL,
	quantity INTEGER NOT NULL,
	active_delta INTEGER NOT NULL,
	reserve_delta INTEGER NOT NULL,
	brand VARCHAR(150) NOT NULL,
	variant VARCHAR(150) NOT NULL,
	amount BIGINT,
	store VARCHAR(150) NOT NULL,
	notes VARCHAR(2000) NOT NULL,
	transaction_id UUID,
	request_id UUID NOT NULL,
	request_hash VARCHAR(64) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_stock_request UNIQUE (user_id, request_id),
	CONSTRAINT ck_stock_event_kind CHECK (kind IN ('purchase','open','finish','adjust')),
	CONSTRAINT ck_stock_event_amount CHECK (quantity BETWEEN 0 AND 10000 AND (amount IS NULL OR amount BETWEEN 0 AND 1000000000000)),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
	FOREIGN KEY(product_id) REFERENCES stock_products (id) ON DELETE CASCADE,
	FOREIGN KEY(transaction_id) REFERENCES ledger_transactions (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_stock_event_product ON stock_events (product_id, event_date);
COMMIT;

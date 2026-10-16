-- Additive Wishlist tables; preserves all existing financial records.
BEGIN;
CREATE TABLE IF NOT EXISTS wishlists (
	id UUID NOT NULL,
	user_id UUID NOT NULL,
	name VARCHAR(150) NOT NULL,
	kind VARCHAR(20) NOT NULL,
	share_hash VARCHAR(64),
	share_mode VARCHAR(10) DEFAULT 'view' NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_wishlist_kind CHECK (kind IN ('things','consumables','games','food','holiday','vehicles','gadgets')),
	CONSTRAINT ck_wishlist_share CHECK (share_mode IN ('view','reserve')),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
	UNIQUE (share_hash)
);
CREATE INDEX IF NOT EXISTS ix_wishlist_owner ON wishlists (user_id);

CREATE TABLE IF NOT EXISTS wishlist_groups (
	id UUID NOT NULL,
	wishlist_id UUID NOT NULL,
	name VARCHAR(150) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(wishlist_id) REFERENCES wishlists (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_wishlist_group_list ON wishlist_groups (wishlist_id);

CREATE TABLE IF NOT EXISTS wishlist_items (
	id UUID NOT NULL,
	group_id UUID NOT NULL,
	name VARCHAR(300) NOT NULL,
	platform VARCHAR(150) NOT NULL,
	brand VARCHAR(150) NOT NULL,
	model VARCHAR(200) NOT NULL,
	color VARCHAR(100) NOT NULL,
	capacity VARCHAR(100) NOT NULL,
	year VARCHAR(20) NOT NULL,
	plate VARCHAR(50) NOT NULL,
	country VARCHAR(100) NOT NULL,
	province VARCHAR(150) NOT NULL,
	city VARCHAR(150) NOT NULL,
	notes TEXT NOT NULL,
	link VARCHAR(2048) NOT NULL,
	price NUMERIC(18, 0),
	priority VARCHAR(10) DEFAULT 'normal' NOT NULL,
	status VARCHAR(12) DEFAULT 'wanted' NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_wishlist_price CHECK (price IS NULL OR price >= 0),
	CONSTRAINT ck_wishlist_priority CHECK (priority IN ('high','normal','low')),
	CONSTRAINT ck_wishlist_status CHECK (status IN ('wanted','sold_out','fulfilled','archived')),
	FOREIGN KEY(group_id) REFERENCES wishlist_groups (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_wishlist_item_group ON wishlist_items (group_id);

CREATE TABLE IF NOT EXISTS wishlist_photos (
	item_id UUID NOT NULL,
	position INTEGER NOT NULL,
	url VARCHAR(2048) NOT NULL,
	PRIMARY KEY (item_id, position),
	FOREIGN KEY(item_id) REFERENCES wishlist_items (id) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS wishlist_reservations (
	item_id UUID NOT NULL,
	user_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (item_id),
	FOREIGN KEY(item_id) REFERENCES wishlist_items (id) ON DELETE CASCADE,
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_wishlist_reservations_user_id ON wishlist_reservations (user_id);
COMMIT;

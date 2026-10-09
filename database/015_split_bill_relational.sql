-- Upgrade 014 -> 015. Run with the application stopped.
-- Use tests/check_split_bill_migration.py --apply for validated, backed-up migration.
BEGIN;
LOCK TABLE split_bill_groups IN ACCESS EXCLUSIVE MODE;
ALTER TABLE split_bill_groups ADD COLUMN name VARCHAR(200), ADD COLUMN start_date DATE, ADD COLUMN end_date DATE;
UPDATE split_bill_groups SET name=document->>'Name', start_date=(document->>'StartDate')::date, end_date=(document->>'EndDate')::date;
ALTER TABLE split_bill_groups ALTER COLUMN name SET NOT NULL, ALTER COLUMN start_date SET NOT NULL, ALTER COLUMN end_date SET NOT NULL,
    ADD CONSTRAINT ck_split_group_name CHECK (length(trim(name)) > 0),
    ADD CONSTRAINT ck_split_group_dates CHECK (start_date >= '2000-01-01' AND end_date >= start_date);
CREATE TABLE split_bill_participants (
	group_id UUID NOT NULL,
	id UUID NOT NULL,
	name VARCHAR(80) NOT NULL,
	position INTEGER NOT NULL,
	PRIMARY KEY (group_id, id),
	CONSTRAINT uq_split_participant_position UNIQUE (group_id, position),
	CONSTRAINT ck_split_participant_position CHECK (position BETWEEN 0 AND 19),
	CONSTRAINT ck_split_participant_name CHECK (length(trim(name)) > 0),
	FOREIGN KEY(group_id) REFERENCES split_bill_groups (id) ON DELETE CASCADE
);

CREATE TABLE split_bill_expenses (
	group_id UUID NOT NULL,
	id UUID NOT NULL,
	name VARCHAR(200) NOT NULL,
	expense_date DATE NOT NULL,
	paid_by UUID NOT NULL,
	service_mode VARCHAR(10) NOT NULL,
	service_value NUMERIC(15, 2) NOT NULL,
	tax_mode VARCHAR(10) NOT NULL,
	tax_value NUMERIC(15, 2) NOT NULL,
	tax_includes_service BOOLEAN NOT NULL,
	fee_allocation VARCHAR(12) NOT NULL,
	receipt_total BIGINT,
	notes VARCHAR(2000) NOT NULL,
	position INTEGER NOT NULL,
	PRIMARY KEY (group_id, id),
	FOREIGN KEY(group_id, paid_by) REFERENCES split_bill_participants (group_id, id),
	CONSTRAINT uq_split_expense_position UNIQUE (group_id, position),
	CONSTRAINT ck_split_expense_position CHECK (position BETWEEN 0 AND 99),
	CONSTRAINT ck_split_expense_name CHECK (length(trim(name)) > 0),
	CONSTRAINT ck_split_service CHECK (service_mode IN ('AMOUNT','PERCENT') AND service_value >= 0 AND service_value <= 1000000000000 AND (service_mode <> 'PERCENT' OR service_value <= 100) AND (service_mode <> 'AMOUNT' OR service_value = round(service_value))),
	CONSTRAINT ck_split_tax CHECK (tax_mode IN ('AMOUNT','PERCENT') AND tax_value >= 0 AND tax_value <= 1000000000000 AND (tax_mode <> 'PERCENT' OR tax_value <= 100) AND (tax_mode <> 'AMOUNT' OR tax_value = round(tax_value))),
	CONSTRAINT ck_split_fee_allocation CHECK (fee_allocation IN ('PROPORTIONAL','EQUAL','MIXED')),
	CONSTRAINT ck_split_receipt_total CHECK (receipt_total IS NULL OR receipt_total BETWEEN 0 AND 1000000000000),
	FOREIGN KEY(group_id) REFERENCES split_bill_groups (id) ON DELETE CASCADE
);

CREATE TABLE split_bill_items (
	group_id UUID NOT NULL,
	expense_id UUID NOT NULL,
	id UUID NOT NULL,
	name VARCHAR(200) NOT NULL,
	amount BIGINT NOT NULL,
	split_mode VARCHAR(6) NOT NULL,
	position INTEGER NOT NULL,
	PRIMARY KEY (group_id, expense_id, id),
	FOREIGN KEY(group_id, expense_id) REFERENCES split_bill_expenses (group_id, id) ON DELETE CASCADE,
	CONSTRAINT uq_split_item_position UNIQUE (group_id, expense_id, position),
	CONSTRAINT ck_split_item_position CHECK (position BETWEEN 0 AND 99),
	CONSTRAINT ck_split_item_name CHECK (length(trim(name)) > 0),
	CONSTRAINT ck_split_item_amount CHECK (amount > 0 AND amount <= 1000000000000),
	CONSTRAINT ck_split_item_mode CHECK (split_mode IN ('EQUAL','CUSTOM'))
);

CREATE TABLE split_bill_shares (
	group_id UUID NOT NULL,
	expense_id UUID NOT NULL,
	item_id UUID NOT NULL,
	participant_id UUID NOT NULL,
	amount BIGINT NOT NULL,
	position INTEGER NOT NULL,
	PRIMARY KEY (group_id, expense_id, item_id, participant_id),
	FOREIGN KEY(group_id, expense_id, item_id) REFERENCES split_bill_items (group_id, expense_id, id) ON DELETE CASCADE,
	FOREIGN KEY(group_id, participant_id) REFERENCES split_bill_participants (group_id, id),
	CONSTRAINT uq_split_share_position UNIQUE (group_id, expense_id, item_id, position),
	CONSTRAINT ck_split_share_position CHECK (position BETWEEN 0 AND 19),
	CONSTRAINT ck_split_share_amount CHECK (amount BETWEEN 0 AND 1000000000000)
);

INSERT INTO split_bill_participants(group_id,id,name,position)
SELECT g.id,(p.value->>'Id')::uuid,p.value->>'Name',p.ordinality-1
FROM split_bill_groups g CROSS JOIN LATERAL jsonb_array_elements(g.document->'Participants') WITH ORDINALITY p;

INSERT INTO split_bill_expenses(group_id,id,name,expense_date,paid_by,service_mode,service_value,tax_mode,tax_value,tax_includes_service,fee_allocation,receipt_total,notes,position)
SELECT g.id,(e.value->>'Id')::uuid,e.value->>'Name',(e.value->>'ExpenseDate')::date,(e.value->>'PaidBy')::uuid,
    COALESCE(e.value->'ServiceCharge'->>'Mode','AMOUNT'),COALESCE((e.value->'ServiceCharge'->>'Value')::numeric,0),
    COALESCE(e.value->'Tax'->>'Mode','AMOUNT'),COALESCE((e.value->'Tax'->>'Value')::numeric,0),
    COALESCE((e.value->>'TaxIncludesService')::boolean,true),COALESCE(e.value->>'FeeAllocation','MIXED'),
    (e.value->>'ReceiptTotal')::bigint,COALESCE(e.value->>'Notes',''),e.ordinality-1
FROM split_bill_groups g CROSS JOIN LATERAL jsonb_array_elements(g.document->'Expenses') WITH ORDINALITY e;

INSERT INTO split_bill_items(group_id,expense_id,id,name,amount,split_mode,position)
SELECT g.id,(e.value->>'Id')::uuid,(i.value->>'Id')::uuid,i.value->>'Name',(i.value->>'Amount')::bigint,COALESCE(i.value->>'SplitMode','EQUAL'),i.ordinality-1
FROM split_bill_groups g CROSS JOIN LATERAL jsonb_array_elements(g.document->'Expenses') e
CROSS JOIN LATERAL jsonb_array_elements(e.value->'Items') WITH ORDINALITY i;

INSERT INTO split_bill_shares(group_id,expense_id,item_id,participant_id,amount,position)
SELECT g.id,(e.value->>'Id')::uuid,(i.value->>'Id')::uuid,(s.value->>'ParticipantId')::uuid,(s.value->>'Amount')::bigint,s.ordinality-1
FROM split_bill_groups g CROSS JOIN LATERAL jsonb_array_elements(g.document->'Expenses') e
CROSS JOIN LATERAL jsonb_array_elements(e.value->'Items') i
CROSS JOIN LATERAL jsonb_array_elements(i.value->'Shares') WITH ORDINALITY s;

-- Fail before removing the source if any group/item is incomplete.
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM split_bill_groups g WHERE (SELECT count(*) FROM split_bill_participants p WHERE p.group_id=g.id) NOT BETWEEN 2 AND 20)
    OR EXISTS (SELECT 1 FROM split_bill_expenses e JOIN split_bill_groups g ON g.id=e.group_id WHERE e.expense_date NOT BETWEEN g.start_date AND g.end_date
        OR NOT EXISTS (SELECT 1 FROM split_bill_items i WHERE i.group_id=e.group_id AND i.expense_id=e.id))
    OR EXISTS (SELECT 1 FROM split_bill_items i WHERE NOT EXISTS (SELECT 1 FROM split_bill_shares s WHERE s.group_id=i.group_id AND s.expense_id=i.expense_id AND s.item_id=i.id)
        OR (i.split_mode='CUSTOM' AND i.amount<>(SELECT sum(s.amount) FROM split_bill_shares s WHERE s.group_id=i.group_id AND s.expense_id=i.expense_id AND s.item_id=i.id)))
    THEN RAISE EXCEPTION 'Invalid legacy Split Bill data; migration cancelled.'; END IF;
END $$;
ALTER TABLE split_bill_groups DROP COLUMN document;
COMMIT;

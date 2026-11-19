-- Read-only PostgreSQL examples for psql after migrate + demo_data.sql.
-- requester_username is selected by the authenticated server, never trusted from a browser.
\set ON_ERROR_STOP on
\set requester_username db_demo_a
\set shipment_number PL20261118001
BEGIN READ ONLY;
SET LOCAL TIME ZONE 'Asia/Shanghai';

-- 1. Customer-scoped list. A user can have only one customer membership.
SELECT s.number, s.status, s.goods_summary, s.current_location,
       s.latest_event_at, s.estimated_delivery_date, s.delivered_at
FROM logistics_shipment AS s
JOIN logistics_customer_user AS m ON m.customer_id = s.customer_id
JOIN logistics_customer AS c ON c.id = m.customer_id AND c.is_active
JOIN auth_user AS u ON u.id = m.user_id AND u.is_active
WHERE u.username = :'requester_username'
ORDER BY s.updated_at DESC, s.id DESC
LIMIT 50 OFFSET 0;

-- 2. Detail and ownership are checked in the same query.
SELECT s.*
FROM logistics_shipment AS s
JOIN logistics_customer_user AS m ON m.customer_id = s.customer_id
JOIN auth_user AS u ON u.id = m.user_id AND u.is_active
JOIN logistics_customer AS c ON c.id = m.customer_id AND c.is_active
WHERE u.username = :'requester_username' AND s.number = :'shipment_number';

-- 3. Customer-scoped event timeline. Old scans remain visible in time order.
SELECT e.status, e.title, e.description, e.location,
       e.occurred_at, e.received_at, e.source
FROM logistics_tracking_event AS e
JOIN logistics_shipment AS s ON s.id = e.shipment_id
JOIN logistics_customer_user AS m ON m.customer_id = s.customer_id
JOIN auth_user AS u ON u.id = m.user_id AND u.is_active
JOIN logistics_customer AS c ON c.id = m.customer_id AND c.is_active
WHERE u.username = :'requester_username' AND s.number = :'shipment_number'
ORDER BY e.occurred_at DESC, e.id DESC
LIMIT 100;

-- 4. Customer totals. These counts do not include other customers' shipments.
SELECT count(*) AS total,
       count(*) FILTER (WHERE s.status = 'warehouse') AS warehouse,
       count(*) FILTER (WHERE s.status IN ('shipped','transit','customs','delivery')) AS moving,
       count(*) FILTER (WHERE s.status = 'delivered') AS delivered
FROM logistics_shipment AS s
JOIN logistics_customer_user AS m ON m.customer_id = s.customer_id
JOIN auth_user AS u ON u.id = m.user_id AND u.is_active
JOIN logistics_customer AS c ON c.id = m.customer_id AND c.is_active
WHERE u.username = :'requester_username';

-- 5. Inspect real columns, constraints, and indexes instead of relying on a diagram.
SELECT table_name, column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name LIKE 'logistics_%'
ORDER BY table_name, ordinal_position;
SELECT conrelid::regclass AS table_name, conname, pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE connamespace = 'public'::regnamespace
  AND conrelid::regclass::text LIKE 'logistics_%'
ORDER BY table_name, conname;
SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public' AND tablename LIKE 'logistics_%'
ORDER BY tablename, indexname;
COMMIT;

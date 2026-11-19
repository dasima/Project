-- Executable psql write examples against development fixtures.
-- Each example rolls back its data changes. Django migrations own production DDL.
-- The Django application writes via logistics.services for auth, validation, and audit.
\set ON_ERROR_STOP on

-- 1. A prealert is unassigned; creating it does not mark a shipment as received.
BEGIN;
INSERT INTO logistics_package
    (customer_id, shipment_id, prealert_number, domestic_tracking_number,
     description, pieces, weight_kg, status, received_at, created_at, updated_at)
SELECT m.customer_id, NULL, 'PA-SQL-REVIEW', 'SFSQLREVIEW01',
       'SQL 示例包裹 海运 吉隆坡', 1, 1.200, 'prealert', NULL, now(), now()
FROM logistics_customer_user m JOIN auth_user u ON u.id=m.user_id
JOIN logistics_customer c ON c.id=m.customer_id AND c.is_active
WHERE u.username='db_demo_a' AND u.is_active
ON CONFLICT (prealert_number) DO NOTHING
RETURNING prealert_number, status;
-- Only an authorized operator may confirm receipt and bind a same-customer shipment.
UPDATE logistics_package p
SET shipment_id=s.id, status='received', received_at=now(), updated_at=now()
FROM logistics_shipment s
WHERE p.prealert_number='PA-SQL-REVIEW' AND s.number='PL20261118001'
  AND p.customer_id=s.customer_id
RETURNING p.prealert_number, p.shipment_id, p.status;
ROLLBACK;

-- 6. Delete only a customer's unassigned, unreceived prealert. Retain shipments,
-- tracking history, and audit records; use controlled correction instead of deletion.
BEGIN;
DELETE FROM logistics_package p
USING logistics_customer_user m, auth_user u
WHERE m.customer_id=p.customer_id AND u.id=m.user_id
  AND u.username='db_demo_a' AND u.is_active
  AND p.prealert_number='PA-SQL-REVIEW'
  AND p.status='prealert' AND p.shipment_id IS NULL AND p.received_at IS NULL
RETURNING p.prealert_number;
ROLLBACK;

-- 2. Append a deduplicated scan and atomically update the current projection.
-- Row lock serializes concurrent events for a shipment; older events never regress it.
BEGIN;
SELECT id FROM logistics_shipment WHERE number='PL20261118001' FOR UPDATE;
WITH inserted AS (
    INSERT INTO logistics_tracking_event
        (shipment_id,source,source_key,status,title,description,location,
         occurred_at,received_at,raw_status,latitude,longitude)
    SELECT id,'manual','sql-review-event-1','customs','目的地清关中',
           'SQL 事务示例','吉隆坡海关','2026-11-19 09:00:00+08',now(),'',NULL,NULL
    FROM logistics_shipment WHERE number='PL20261118001'
    ON CONFLICT (shipment_id,source_key) DO NOTHING
    RETURNING *
), projected AS (
    UPDATE logistics_shipment s
    SET status=e.status,current_location=e.location,latest_event_at=e.occurred_at,
        delivered_at=CASE WHEN e.status='delivered' THEN e.occurred_at ELSE NULL END,
        updated_at=now()
    FROM inserted e
    WHERE s.id=e.shipment_id
      AND (s.latest_event_at IS NULL OR e.occurred_at>=s.latest_event_at)
    RETURNING s.id
)
INSERT INTO logistics_audit_log(actor_id,shipment_id,action,reason,changes,created_at)
SELECT u.id,e.shipment_id,'tracking_event.add','SQL操作演示',
       jsonb_build_object('event_id',e.id,'source_key',e.source_key,
                          'projection_updated',EXISTS(SELECT 1 FROM projected)),now()
FROM inserted e CROSS JOIN auth_user u
WHERE u.username='db_operator' AND u.is_active AND u.is_superuser
RETURNING shipment_id,action,changes;
ROLLBACK;

-- 3. Multiple workers claim distinct jobs using row locks and a time-bounded lease.
BEGIN;
WITH candidates AS (
    SELECT id FROM logistics_sync_job
    WHERE status IN ('pending','failed') AND next_retry_at<=now()
    ORDER BY next_retry_at,id
    FOR UPDATE SKIP LOCKED LIMIT 10
)
UPDATE logistics_sync_job j
SET status='running',locked_until=now()+interval '5 minutes',
    attempt_count=j.attempt_count+1,updated_at=now()
FROM candidates c WHERE j.id=c.id
RETURNING j.id,j.shipment_id,j.locked_until,j.attempt_count;
-- A worker must retain the returned locked_until as a lease token. A stale worker
-- must not complete a job after a later worker has acquired a replacement lease.
ROLLBACK;

-- 4. Retry/recover jobs whose worker lease expired. Old worker must stop publishing.
BEGIN;
UPDATE logistics_sync_job
SET status='failed',locked_until=NULL,next_retry_at=now()+interval '5 minutes',
    last_error='worker lease expired',updated_at=now()
WHERE status='running' AND locked_until<now()
RETURNING id,shipment_id,next_retry_at;
ROLLBACK;

-- 5. Persist an already signature-verified callback, deduplicating provider retries.
-- Verification happens in the provider adapter before this INSERT; SQL cannot verify HTTPS signatures.
BEGIN;
INSERT INTO logistics_webhook_receipt
    (carrier_id,event_key,payload,received_at,processed_at,status,attempt_count,last_error)
SELECT id,'sql-review-webhook-1','{"demo":true}'::jsonb,now(),NULL,'pending',0,''
FROM logistics_carrier WHERE code='DEMO'
ON CONFLICT (carrier_id,event_key) DO NOTHING
RETURNING id,status;
ROLLBACK;

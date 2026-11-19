-- PostgreSQL 17 development fixtures. Run after Django migrate.
-- Users have unusable passwords; enable local login with manage.py changepassword.
-- Example recipients are fictional. Re-running does not overwrite existing rows.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL TIME ZONE 'UTC';

INSERT INTO logistics_customer (code, name, email, phone, is_active, created_at, updated_at)
VALUES ('DEMO-A', '演示客户 A', '', '', TRUE, '2026-11-18 00:00:00+00', '2026-11-18 00:00:00+00')
ON CONFLICT DO NOTHING;

INSERT INTO logistics_customer (code, name, email, phone, is_active, created_at, updated_at)
VALUES ('DEMO-B', '演示客户 B', '', '', TRUE, '2026-11-18 00:00:00+00', '2026-11-18 00:00:00+00')
ON CONFLICT DO NOTHING;

INSERT INTO auth_user (username, password, first_name, last_name, email, is_staff, is_superuser, is_active, date_joined, last_login)
VALUES ('db_demo_a', '!database-fixture-disabled', '客户 A', '', '', FALSE, FALSE, TRUE, '2026-11-18 00:00:00+00', NULL)
ON CONFLICT DO NOTHING;

INSERT INTO auth_user (username, password, first_name, last_name, email, is_staff, is_superuser, is_active, date_joined, last_login)
VALUES ('db_demo_b', '!database-fixture-disabled', '客户 B', '', '', FALSE, FALSE, TRUE, '2026-11-18 00:00:00+00', NULL)
ON CONFLICT DO NOTHING;

INSERT INTO auth_user (username, password, first_name, last_name, email, is_staff, is_superuser, is_active, date_joined, last_login)
VALUES ('db_operator', '!database-fixture-disabled', '演示管理员', '', '', TRUE, TRUE, TRUE, '2026-11-18 00:00:00+00', NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_customer_user (user_id, customer_id, created_at)
VALUES ((SELECT id FROM auth_user WHERE username = 'db_demo_a'), (SELECT id FROM logistics_customer WHERE code = 'DEMO-A'), '2026-11-18 00:00:00+00')
ON CONFLICT DO NOTHING;

INSERT INTO logistics_customer_user (user_id, customer_id, created_at)
VALUES ((SELECT id FROM auth_user WHERE username = 'db_demo_b'), (SELECT id FROM logistics_customer WHERE code = 'DEMO-B'), '2026-11-18 00:00:00+00')
ON CONFLICT DO NOTHING;

INSERT INTO logistics_carrier (code, name, api_base_url, is_active, created_at, updated_at)
VALUES ('DEMO', '演示承运商', '', TRUE, '2026-11-18 00:00:00+00', '2026-11-18 00:00:00+00')
ON CONFLICT DO NOTHING;

INSERT INTO logistics_shipment (number, customer_id, carrier_id, carrier_account, tracking_number, goods_summary, transport_method, origin_country, origin_city, destination_country, destination_city, recipient_name, recipient_phone, recipient_address, status, pieces, weight_kg, volume_cbm, estimated_delivery_date, delivered_at, current_location, latest_event_at, created_at, updated_at)
VALUES ('PL20261118001', (SELECT id FROM logistics_customer WHERE code = 'DEMO-A'), (SELECT id FROM logistics_carrier WHERE code = 'DEMO'), 'demo', 'EXT-PL20261118001', '家居好物 · 生活用品', '海运专线', '中国', '深圳', '马来西亚', '吉隆坡', '林先生', '+60 12-345 6789', '18 Jalan Ampang, Kuala Lumpur, Malaysia', 'transit', 3, 12.8, 0.08, '2026-11-22', NULL, '马六甲海峡', '2026-11-18 10:30:00+08', '2026-11-12 16:30:00+08', '2026-11-18 10:30:00+08')
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118001'), 'manual', 'demo:PL20261118001:0', 'warehouse', '包裹已入库', '3 件包裹已入库，称重及查验完成。', '深圳集运仓', '2026-11-12 16:30:00+08', '2026-11-12 16:30:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118001'), 'manual', 'demo:PL20261118001:1', 'shipped', '包裹已出库', '包裹已完成集运装柜，离开深圳仓库。', '深圳盐田港', '2026-11-14 09:45:00+08', '2026-11-14 09:45:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118001'), 'manual', 'demo:PL20261118001:2', 'transit', '干线运输中', '货物已装船，正在进行国际海运。', '南海海域', '2026-11-16 14:20:00+08', '2026-11-16 14:20:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118001'), 'manual', 'demo:PL20261118001:3', 'transit', '干线运输中', '货船正经过马六甲海峡，按计划驶向马来西亚。', '马六甲海峡', '2026-11-18 10:30:00+08', '2026-11-18 10:30:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_package (customer_id, shipment_id, prealert_number, domestic_tracking_number, description, pieces, weight_kg, status, received_at, created_at, updated_at)
VALUES ((SELECT id FROM logistics_customer WHERE code = 'DEMO-A'), (SELECT id FROM logistics_shipment WHERE number = 'PL20261118001'), 'PA-PL20261118001', 'SFDEMO61118001', '家居好物 · 生活用品', 3, 12.8, 'packed', '2026-11-12 16:30:00+08', '2026-11-12 16:30:00+08', '2026-11-18 10:30:00+08')
ON CONFLICT DO NOTHING;

INSERT INTO logistics_sync_job (shipment_id, status, attempt_count, next_retry_at, locked_until, last_success_at, last_error, created_at, updated_at)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118001'), 'pending', 0, '2026-11-18 00:00:00+00', NULL, NULL, '', '2026-11-18 00:00:00+00', '2026-11-18 00:00:00+00')
ON CONFLICT DO NOTHING;

INSERT INTO logistics_shipment (number, customer_id, carrier_id, carrier_account, tracking_number, goods_summary, transport_method, origin_country, origin_city, destination_country, destination_city, recipient_name, recipient_phone, recipient_address, status, pieces, weight_kg, volume_cbm, estimated_delivery_date, delivered_at, current_location, latest_event_at, created_at, updated_at)
VALUES ('PL20261118002', (SELECT id FROM logistics_customer WHERE code = 'DEMO-A'), (SELECT id FROM logistics_carrier WHERE code = 'DEMO'), 'demo', 'EXT-PL20261118002', '时尚穿搭 · 服装鞋包', '空运专线', '中国', '深圳', '新加坡', '新加坡', '林先生', '+65 8123 4567', '10 Anson Road, Singapore 079903', 'customs', 2, 6.4, 0.04, '2026-11-19', NULL, '新加坡海关', '2026-11-18 09:15:00+08', '2026-11-14 11:20:00+08', '2026-11-18 09:15:00+08')
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118002'), 'manual', 'demo:PL20261118002:0', 'warehouse', '包裹已入库', '2 件包裹已入库，等待安排航班。', '深圳集运仓', '2026-11-14 11:20:00+08', '2026-11-14 11:20:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118002'), 'manual', 'demo:PL20261118002:1', 'shipped', '包裹已出库', '包裹已出库并交付航空承运商。', '深圳宝安机场', '2026-11-16 12:00:00+08', '2026-11-16 12:00:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118002'), 'manual', 'demo:PL20261118002:2', 'transit', '干线运输中', '航班已落地，货物等待转交海关。', '新加坡樟宜机场', '2026-11-17 18:40:00+08', '2026-11-17 18:40:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118002'), 'manual', 'demo:PL20261118002:3', 'customs', '目的地清关中', '货物已抵达新加坡，正在办理进口清关手续。', '新加坡海关', '2026-11-18 09:15:00+08', '2026-11-18 09:15:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_package (customer_id, shipment_id, prealert_number, domestic_tracking_number, description, pieces, weight_kg, status, received_at, created_at, updated_at)
VALUES ((SELECT id FROM logistics_customer WHERE code = 'DEMO-A'), (SELECT id FROM logistics_shipment WHERE number = 'PL20261118002'), 'PA-PL20261118002', 'SFDEMO61118002', '时尚穿搭 · 服装鞋包', 2, 6.4, 'packed', '2026-11-14 11:20:00+08', '2026-11-14 11:20:00+08', '2026-11-18 09:15:00+08')
ON CONFLICT DO NOTHING;

INSERT INTO logistics_sync_job (shipment_id, status, attempt_count, next_retry_at, locked_until, last_success_at, last_error, created_at, updated_at)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118002'), 'pending', 0, '2026-11-18 00:00:00+00', NULL, NULL, '', '2026-11-18 00:00:00+00', '2026-11-18 00:00:00+00')
ON CONFLICT DO NOTHING;

INSERT INTO logistics_shipment (number, customer_id, carrier_id, carrier_account, tracking_number, goods_summary, transport_method, origin_country, origin_city, destination_country, destination_city, recipient_name, recipient_phone, recipient_address, status, pieces, weight_kg, volume_cbm, estimated_delivery_date, delivered_at, current_location, latest_event_at, created_at, updated_at)
VALUES ('PL20261118003', (SELECT id FROM logistics_customer WHERE code = 'DEMO-A'), (SELECT id FROM logistics_carrier WHERE code = 'DEMO'), 'demo', 'EXT-PL20261118003', '数码配件 · 办公用品', '海运专线', '中国', '广州', '马来西亚', '吉隆坡', '林先生', '+60 12-345 6789', '18 Jalan Ampang, Kuala Lumpur, Malaysia', 'warehouse', 4, 8.2, 0.06, '2026-11-26', NULL, '广州集运仓', '2026-11-18 08:20:00+08', '2026-11-18 08:20:00+08', '2026-11-18 08:20:00+08')
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118003'), 'manual', 'demo:PL20261118003:0', 'warehouse', '包裹已入库', '4 件包裹已完成入库，正在安排合箱和出库。', '广州集运仓', '2026-11-18 08:20:00+08', '2026-11-18 08:20:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_package (customer_id, shipment_id, prealert_number, domestic_tracking_number, description, pieces, weight_kg, status, received_at, created_at, updated_at)
VALUES ((SELECT id FROM logistics_customer WHERE code = 'DEMO-A'), (SELECT id FROM logistics_shipment WHERE number = 'PL20261118003'), 'PA-PL20261118003', 'SFDEMO61118003', '数码配件 · 办公用品', 4, 8.2, 'received', '2026-11-18 08:20:00+08', '2026-11-18 08:20:00+08', '2026-11-18 08:20:00+08')
ON CONFLICT DO NOTHING;

INSERT INTO logistics_sync_job (shipment_id, status, attempt_count, next_retry_at, locked_until, last_success_at, last_error, created_at, updated_at)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118003'), 'pending', 0, '2026-11-18 00:00:00+00', NULL, NULL, '', '2026-11-18 00:00:00+00', '2026-11-18 00:00:00+00')
ON CONFLICT DO NOTHING;

INSERT INTO logistics_shipment (number, customer_id, carrier_id, carrier_account, tracking_number, goods_summary, transport_method, origin_country, origin_city, destination_country, destination_city, recipient_name, recipient_phone, recipient_address, status, pieces, weight_kg, volume_cbm, estimated_delivery_date, delivered_at, current_location, latest_event_at, created_at, updated_at)
VALUES ('PL20261118004', (SELECT id FROM logistics_customer WHERE code = 'DEMO-A'), (SELECT id FROM logistics_carrier WHERE code = 'DEMO'), 'demo', 'EXT-PL20261118004', '美妆护肤 · 个人护理', '空运专线', '中国', '义乌', '泰国', '曼谷', '林先生', '+66 81 234 5678', '88 Sukhumvit Road, Bangkok, Thailand', 'delivery', 2, 5.6, 0.03, '2026-11-18', NULL, '曼谷配送站', '2026-11-18 09:45:00+08', '2026-11-13 10:15:00+08', '2026-11-18 09:45:00+08')
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118004'), 'manual', 'demo:PL20261118004:0', 'warehouse', '包裹已入库', '包裹入库完成，正在安排运输。', '义乌集运仓', '2026-11-13 10:15:00+08', '2026-11-13 10:15:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118004'), 'manual', 'demo:PL20261118004:1', 'shipped', '包裹已出库', '包裹已出库并交付航空承运商。', '义乌集运仓', '2026-11-14 13:00:00+08', '2026-11-14 13:00:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118004'), 'manual', 'demo:PL20261118004:2', 'transit', '干线运输中', '货物已抵达目的地机场。', '曼谷素万那普机场', '2026-11-16 17:10:00+08', '2026-11-16 17:10:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118004'), 'manual', 'demo:PL20261118004:3', 'customs', '目的地清关中', '进口清关完成，货物已放行。', '曼谷海关', '2026-11-17 15:20:00+08', '2026-11-17 15:20:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118004'), 'manual', 'demo:PL20261118004:4', 'delivery', '当地派送中', '包裹已交由当地配送员，预计今日送达。', '曼谷配送站', '2026-11-18 09:45:00+08', '2026-11-18 09:45:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_package (customer_id, shipment_id, prealert_number, domestic_tracking_number, description, pieces, weight_kg, status, received_at, created_at, updated_at)
VALUES ((SELECT id FROM logistics_customer WHERE code = 'DEMO-A'), (SELECT id FROM logistics_shipment WHERE number = 'PL20261118004'), 'PA-PL20261118004', 'SFDEMO61118004', '美妆护肤 · 个人护理', 2, 5.6, 'packed', '2026-11-13 10:15:00+08', '2026-11-13 10:15:00+08', '2026-11-18 09:45:00+08')
ON CONFLICT DO NOTHING;

INSERT INTO logistics_sync_job (shipment_id, status, attempt_count, next_retry_at, locked_until, last_success_at, last_error, created_at, updated_at)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118004'), 'pending', 0, '2026-11-18 00:00:00+00', NULL, NULL, '', '2026-11-18 00:00:00+00', '2026-11-18 00:00:00+00')
ON CONFLICT DO NOTHING;

INSERT INTO logistics_shipment (number, customer_id, carrier_id, carrier_account, tracking_number, goods_summary, transport_method, origin_country, origin_city, destination_country, destination_city, recipient_name, recipient_phone, recipient_address, status, pieces, weight_kg, volume_cbm, estimated_delivery_date, delivered_at, current_location, latest_event_at, created_at, updated_at)
VALUES ('PL20261118005', (SELECT id FROM logistics_customer WHERE code = 'DEMO-A'), (SELECT id FROM logistics_carrier WHERE code = 'DEMO'), 'demo', 'EXT-PL20261118005', '家居收纳 · 小型家具', '海运专线', '中国', '深圳', '马来西亚', '吉隆坡', '林先生', '+60 12-345 6789', '18 Jalan Ampang, Kuala Lumpur, Malaysia', 'delivered', 5, 18.5, 0.16, '2026-11-16', '2026-11-16 16:35:00+08', '吉隆坡 · 已签收', '2026-11-16 16:35:00+08', '2026-11-06 15:40:00+08', '2026-11-16 16:35:00+08')
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118005'), 'manual', 'demo:PL20261118005:0', 'warehouse', '包裹已入库', '5 件包裹已完成入库和查验。', '深圳集运仓', '2026-11-06 15:40:00+08', '2026-11-06 15:40:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118005'), 'manual', 'demo:PL20261118005:1', 'shipped', '包裹已出库', '包裹已装柜出港。', '深圳盐田港', '2026-11-08 09:00:00+08', '2026-11-08 09:00:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118005'), 'manual', 'demo:PL20261118005:2', 'transit', '干线运输中', '货船抵达巴生港，等待卸柜。', '巴生港', '2026-11-14 06:30:00+08', '2026-11-14 06:30:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118005'), 'manual', 'demo:PL20261118005:3', 'customs', '目的地清关中', '货物已完成清关并放行。', '吉隆坡海关', '2026-11-15 11:10:00+08', '2026-11-15 11:10:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118005'), 'manual', 'demo:PL20261118005:4', 'delivery', '当地派送中', '包裹正在派送，请保持电话畅通。', '吉隆坡配送站', '2026-11-16 08:50:00+08', '2026-11-16 08:50:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118005'), 'manual', 'demo:PL20261118005:5', 'delivered', '已签收', '包裹已由收件人本人签收，感谢您的信任。', '吉隆坡收货地址', '2026-11-16 16:35:00+08', '2026-11-16 16:35:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_package (customer_id, shipment_id, prealert_number, domestic_tracking_number, description, pieces, weight_kg, status, received_at, created_at, updated_at)
VALUES ((SELECT id FROM logistics_customer WHERE code = 'DEMO-A'), (SELECT id FROM logistics_shipment WHERE number = 'PL20261118005'), 'PA-PL20261118005', 'SFDEMO61118005', '家居收纳 · 小型家具', 5, 18.5, 'packed', '2026-11-06 15:40:00+08', '2026-11-06 15:40:00+08', '2026-11-16 16:35:00+08')
ON CONFLICT DO NOTHING;

INSERT INTO logistics_shipment (number, customer_id, carrier_id, carrier_account, tracking_number, goods_summary, transport_method, origin_country, origin_city, destination_country, destination_city, recipient_name, recipient_phone, recipient_address, status, pieces, weight_kg, volume_cbm, estimated_delivery_date, delivered_at, current_location, latest_event_at, created_at, updated_at)
VALUES ('PL20261118006', (SELECT id FROM logistics_customer WHERE code = 'DEMO-A'), (SELECT id FROM logistics_carrier WHERE code = 'DEMO'), 'demo', 'EXT-PL20261118006', '茶饮零食 · 食品礼盒', '空运专线', '中国', '广州', '马来西亚', '吉隆坡', '林先生', '+60 12-345 6789', '18 Jalan Ampang, Kuala Lumpur, Malaysia', 'delivered', 1, 3.2, 0.02, '2026-11-15', '2026-11-15 14:10:00+08', '吉隆坡 · 已签收', '2026-11-15 14:10:00+08', '2026-11-10 12:20:00+08', '2026-11-15 14:10:00+08')
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118006'), 'manual', 'demo:PL20261118006:0', 'warehouse', '包裹已入库', '包裹已完成入库及称重。', '广州集运仓', '2026-11-10 12:20:00+08', '2026-11-10 12:20:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118006'), 'manual', 'demo:PL20261118006:1', 'shipped', '包裹已出库', '包裹已交付航空承运商。', '广州白云机场', '2026-11-12 08:30:00+08', '2026-11-12 08:30:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118006'), 'manual', 'demo:PL20261118006:2', 'transit', '干线运输中', '货物已抵达目的地机场。', '吉隆坡国际机场', '2026-11-13 18:15:00+08', '2026-11-13 18:15:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118006'), 'manual', 'demo:PL20261118006:3', 'customs', '目的地清关中', '清关完成，包裹已放行。', '吉隆坡海关', '2026-11-14 13:40:00+08', '2026-11-14 13:40:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118006'), 'manual', 'demo:PL20261118006:4', 'delivery', '当地派送中', '包裹已安排当地配送。', '吉隆坡配送站', '2026-11-15 09:05:00+08', '2026-11-15 09:05:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_tracking_event (shipment_id, source, source_key, status, title, description, location, occurred_at, received_at, raw_status, latitude, longitude)
VALUES ((SELECT id FROM logistics_shipment WHERE number = 'PL20261118006'), 'manual', 'demo:PL20261118006:5', 'delivered', '已签收', '包裹已由收件人本人签收。', '吉隆坡收货地址', '2026-11-15 14:10:00+08', '2026-11-15 14:10:00+08', '', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO logistics_package (customer_id, shipment_id, prealert_number, domestic_tracking_number, description, pieces, weight_kg, status, received_at, created_at, updated_at)
VALUES ((SELECT id FROM logistics_customer WHERE code = 'DEMO-A'), (SELECT id FROM logistics_shipment WHERE number = 'PL20261118006'), 'PA-PL20261118006', 'SFDEMO61118006', '茶饮零食 · 食品礼盒', 1, 3.2, 'packed', '2026-11-10 12:20:00+08', '2026-11-10 12:20:00+08', '2026-11-15 14:10:00+08')
ON CONFLICT DO NOTHING;

INSERT INTO logistics_shipment (number, customer_id, carrier_id, carrier_account, tracking_number, goods_summary, transport_method, origin_country, origin_city, destination_country, destination_city, recipient_name, recipient_phone, recipient_address, status, pieces, weight_kg, volume_cbm, estimated_delivery_date, delivered_at, current_location, latest_event_at, created_at, updated_at)
VALUES ('PL20261118B01', (SELECT id FROM logistics_customer WHERE code = 'DEMO-B'), NULL, '', '', '客户 B 专属演示包裹', '海运专线', '中国', '深圳', '马来西亚', '吉隆坡', '演示客户 B', '000-00000000', '演示地址 待确认', 'warehouse', 1, NULL, NULL, NULL, NULL, '待入库确认', NULL, '2026-11-18 00:00:00+00', '2026-11-18 00:00:00+00')
ON CONFLICT DO NOTHING;

COMMIT;

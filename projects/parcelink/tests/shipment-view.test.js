import test from 'node:test';
import assert from 'node:assert/strict';
import { deliveryDate, validTrackingNumber } from '../shipment-view.js';

test('signed shipments show the actual delivery event date instead of the original ETA', () => {
  assert.equal(deliveryDate({status:'delivered',eta:'2026-11-22',updatedAt:'2026-11-18 11:30',timeline:[{status:'delivered',time:'2026-11-18 11:30'}]}),'2026-11-18');
  assert.equal(deliveryDate({status:'transit',eta:'2026-11-22',timeline:[]}),'2026-11-22');
});
test('tracking numbers reject malformed and too-short input', () => {
  assert.equal(validTrackingNumber('SF1234567890123'),true);
  assert.equal(validTrackingNumber('YT-123456'),true);
  assert.equal(validTrackingNumber('!!!'),false);
  assert.equal(validTrackingNumber('ABC'),false);
  assert.equal(validTrackingNumber('<img onerror=x>'),false);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import {
  authenticate,
  filterShipments,
  getShipments,
  getStats,
  saveShipments,
  updateShipment,
} from '../data.js';

const memoryStorage = () => {
  const entries = new Map();
  return {
    getItem: (key) => entries.get(key) ?? null,
    setItem: (key, value) => entries.set(key, value),
  };
};

test('authentication accepts the account for its role and rejects invalid credentials', () => {
  assert.deepEqual(authenticate('customer', 'demo', '123456'), {
    role: 'customer', name: '林先生', username: 'demo',
  });
  assert.deepEqual(authenticate('admin', 'admin', '123456'), {
    role: 'admin', name: '运营管理员', username: 'admin',
  });
  assert.equal(authenticate('customer', 'admin', '123456'), null);
  assert.equal(authenticate('admin', 'admin', 'wrong'), null);
  assert.equal(authenticate('owner', 'admin', '123456'), null);
  assert.equal(authenticate('customer', '', ''), null);
});

test('query matches identifiers without case sensitivity and combines with the status filter', () => {
  const shipments = getShipments(null);
  assert.deepEqual(filterShipments(shipments, {
    query: ' pl20261118001 ', status: 'transit',
  }).map(({ id }) => id), ['PL20261118001']);
  assert.equal(filterShipments(shipments, {
    query: 'PL20261118001', status: 'delivered',
  }).length, 0);
  assert.equal(filterShipments(shipments, { query: '不存在的包裹' }).length, 0);
});

test('query searches goods, origin, destination, and current location', () => {
  const shipments = getShipments(null);
  for (const query of ['家居好物', '深圳', '吉隆坡', '马六甲海峡']) {
    assert.ok(filterShipments(shipments, { query }).some(({ id }) => id === 'PL20261118001'));
  }
});

test('statistics group all active transport stages as transit', () => {
  assert.deepEqual(getStats(getShipments(null)), {
    total: 6, transit: 3, warehouse: 1, delivered: 2,
  });
  assert.deepEqual(getStats([
    { status: 'warehouse' }, { status: 'shipped' }, { status: 'transit' },
    { status: 'customs' }, { status: 'delivery' }, { status: 'delivered' },
  ]), { total: 6, transit: 4, warehouse: 1, delivered: 1 });
});

test('updating a shipment preserves original data and prepends the latest timeline event', () => {
  const shipments = getShipments(null);
  const before = structuredClone(shipments);
  const updated = updateShipment(shipments, 'PL20261118001', {
    status: 'delivered', location: '  吉隆坡收货地址  ', note: '  收件人已签收  ',
  });
  assert.notEqual(updated, shipments);
  assert.deepEqual(shipments, before);
  assert.equal(updated[1], shipments[1]);
  assert.notEqual(updated[0], shipments[0]);
  assert.equal(updated[0].status, 'delivered');
  assert.equal(updated[0].location, '吉隆坡收货地址');
  assert.equal(updated[0].progress, 100);
  assert.match(updated[0].updatedAt, /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
  assert.equal(updated[0].timeline.length, before[0].timeline.length + 1);
  assert.deepEqual(updated[0].timeline[0], {
    title: '已签收', description: '收件人已签收', location: '吉隆坡收货地址',
    time: updated[0].updatedAt, status: 'delivered',
  });
  assert.deepEqual(updated[0].timeline.slice(1), before[0].timeline);
});

test('updating a shipment rejects unknown status, blank details, and unknown identifiers', () => {
  const shipments = getShipments(null);
  const valid = { status: 'customs', location: '吉隆坡海关', note: '正在办理清关' };
  assert.throws(() => updateShipment(shipments, shipments[0].id, { ...valid, status: 'lost' }));
  assert.throws(() => updateShipment(shipments, shipments[0].id, { ...valid, location: ' ' }));
  assert.throws(() => updateShipment(shipments, shipments[0].id, { ...valid, note: '' }));
  assert.throws(() => updateShipment(shipments, 'missing', valid));
});

test('saved updates survive a storage round trip', () => {
  const storage = memoryStorage();
  const updated = updateShipment(getShipments(null), 'PL20261118001', {
    status: 'customs', location: '吉隆坡海关', note: '货物已抵达，等待清关',
  });
  assert.equal(saveShipments(updated, storage), true);
  assert.deepEqual(getShipments(storage), updated);
  assert.notEqual(getShipments(storage)[0], updated[0]);
});

test('missing, malformed, or unavailable storage falls back to independent sample data', () => {
  for (const storage of [
    null,
    memoryStorage(),
    { getItem: () => '{invalid json' },
    { getItem: () => '{}' },
    { getItem: () => '[{"id":"bad"}]' },
    { getItem: () => { throw new Error('storage unavailable'); } },
  ]) {
    const shipments = getShipments(storage);
    assert.equal(shipments.length, 6);
    shipments[0].origin.city = 'changed';
    shipments[0].timeline[0].description = 'changed';
    assert.equal(getShipments(storage)[0].origin.city, '深圳');
    assert.notEqual(getShipments(storage)[0].timeline[0].description, 'changed');
  }
  assert.equal(saveShipments(getShipments(null), null), false);
  assert.equal(saveShipments(getShipments(null), {
    setItem: () => { throw new Error('quota exceeded'); },
  }), false);
});

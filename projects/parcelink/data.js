const STORAGE_KEY = 'parcelink_shipments_v1';

export const STATUS_OPTIONS = [
  { id: 'warehouse', label: '待出库', color: 'gray', step: 0 },
  { id: 'shipped', label: '已发货', color: 'blue', step: 1 },
  { id: 'transit', label: '运输中', color: 'blue', step: 2 },
  { id: 'customs', label: '清关中', color: 'amber', step: 3 },
  { id: 'delivery', label: '派送中', color: 'blue', step: 4 },
  { id: 'delivered', label: '已签收', color: 'green', step: 5 },
];

export const DEMO_ACCOUNTS = {
  customer: { username: 'demo', password: '123456' },
  admin: { username: 'admin', password: '123456' },
};

const STATUS_PROGRESS = { warehouse: 12, shipped: 32, transit: 62, customs: 78, delivery: 92, delivered: 100 };
const TIMELINE_TITLES = {
  warehouse: '包裹已入库', shipped: '包裹已出库', transit: '干线运输中',
  customs: '目的地清关中', delivery: '当地派送中', delivered: '已签收',
};
const cities = {
  shenzhen: { city: '深圳', country: '中国', code: 'SZX' },
  guangzhou: { city: '广州', country: '中国', code: 'CAN' },
  yiwu: { city: '义乌', country: '中国', code: 'YIW' },
  kualaLumpur: { city: '吉隆坡', country: '马来西亚', code: 'KUL' },
  singapore: { city: '新加坡', country: '新加坡', code: 'SIN' },
  bangkok: { city: '曼谷', country: '泰国', code: 'BKK' },
};

const event = (status, location, time, description) => ({
  title: TIMELINE_TITLES[status], description, location, time, status,
});

const sampleShipment = ({ origin = cities.shenzhen, destination = cities.kualaLumpur, recipient, ...details }) => ({
  origin,
  destination,
  recipient: recipient ?? {
    name: '林先生', phone: '+60 12-345 6789',
    address: '18 Jalan Ampang, Kuala Lumpur, Malaysia',
  },
  progress: STATUS_PROGRESS[details.status],
  ...details,
});

// These are demonstration shipments dated November 2026, not live carrier data.
const SAMPLE_SHIPMENTS = [
  sampleShipment({
    id: 'PL20261118001', status: 'transit', goods: '家居好物 · 生活用品',
    pieces: 3, weight: 12.8, volume: 0.08, method: '海运专线',
    location: '马六甲海峡', eta: '2026-11-22', createdAt: '2026-11-12', updatedAt: '2026-11-18 10:30',
    timeline: [
      event('transit', '马六甲海峡', '2026-11-18 10:30', '货船正经过马六甲海峡，按计划驶向马来西亚。'),
      event('transit', '南海海域', '2026-11-16 14:20', '货物已装船，正在进行国际海运。'),
      event('shipped', '深圳盐田港', '2026-11-14 09:45', '包裹已完成集运装柜，离开深圳仓库。'),
      event('warehouse', '深圳集运仓', '2026-11-12 16:30', '3 件包裹已入库，称重及查验完成。'),
    ],
  }),
  sampleShipment({
    id: 'PL20261118002', status: 'customs', goods: '时尚穿搭 · 服装鞋包',
    pieces: 2, weight: 6.4, volume: 0.04, method: '空运专线', destination: cities.singapore,
    location: '新加坡海关', eta: '2026-11-19', createdAt: '2026-11-14', updatedAt: '2026-11-18 09:15',
    recipient: { name: '林先生', phone: '+65 8123 4567', address: '10 Anson Road, Singapore 079903' },
    timeline: [
      event('customs', '新加坡海关', '2026-11-18 09:15', '货物已抵达新加坡，正在办理进口清关手续。'),
      event('transit', '新加坡樟宜机场', '2026-11-17 18:40', '航班已落地，货物等待转交海关。'),
      event('shipped', '深圳宝安机场', '2026-11-16 12:00', '包裹已出库并交付航空承运商。'),
      event('warehouse', '深圳集运仓', '2026-11-14 11:20', '2 件包裹已入库，等待安排航班。'),
    ],
  }),
  sampleShipment({
    id: 'PL20261118003', status: 'warehouse', goods: '数码配件 · 办公用品',
    pieces: 4, weight: 8.2, volume: 0.06, method: '海运专线', origin: cities.guangzhou,
    location: '广州集运仓', eta: '2026-11-26', createdAt: '2026-11-18', updatedAt: '2026-11-18 08:20',
    timeline: [event('warehouse', '广州集运仓', '2026-11-18 08:20', '4 件包裹已完成入库，正在安排合箱和出库。')],
  }),
  sampleShipment({
    id: 'PL20261118004', status: 'delivery', goods: '美妆护肤 · 个人护理',
    pieces: 2, weight: 5.6, volume: 0.03, method: '空运专线', origin: cities.yiwu, destination: cities.bangkok,
    location: '曼谷配送站', eta: '2026-11-18', createdAt: '2026-11-13', updatedAt: '2026-11-18 09:45',
    recipient: { name: '林先生', phone: '+66 81 234 5678', address: '88 Sukhumvit Road, Bangkok, Thailand' },
    timeline: [
      event('delivery', '曼谷配送站', '2026-11-18 09:45', '包裹已交由当地配送员，预计今日送达。'),
      event('customs', '曼谷海关', '2026-11-17 15:20', '进口清关完成，货物已放行。'),
      event('transit', '曼谷素万那普机场', '2026-11-16 17:10', '货物已抵达目的地机场。'),
      event('shipped', '义乌集运仓', '2026-11-14 13:00', '包裹已出库并交付航空承运商。'),
      event('warehouse', '义乌集运仓', '2026-11-13 10:15', '包裹入库完成，正在安排运输。'),
    ],
  }),
  sampleShipment({
    id: 'PL20261118005', status: 'delivered', goods: '家居收纳 · 小型家具',
    pieces: 5, weight: 18.5, volume: 0.16, method: '海运专线',
    location: '吉隆坡 · 已签收', eta: '2026-11-16', createdAt: '2026-11-06', updatedAt: '2026-11-16 16:35',
    timeline: [
      event('delivered', '吉隆坡收货地址', '2026-11-16 16:35', '包裹已由收件人本人签收，感谢您的信任。'),
      event('delivery', '吉隆坡配送站', '2026-11-16 08:50', '包裹正在派送，请保持电话畅通。'),
      event('customs', '吉隆坡海关', '2026-11-15 11:10', '货物已完成清关并放行。'),
      event('transit', '巴生港', '2026-11-14 06:30', '货船抵达巴生港，等待卸柜。'),
      event('shipped', '深圳盐田港', '2026-11-08 09:00', '包裹已装柜出港。'),
      event('warehouse', '深圳集运仓', '2026-11-06 15:40', '5 件包裹已完成入库和查验。'),
    ],
  }),
  sampleShipment({
    id: 'PL20261118006', status: 'delivered', goods: '茶饮零食 · 食品礼盒',
    pieces: 1, weight: 3.2, volume: 0.02, method: '空运专线', origin: cities.guangzhou,
    location: '吉隆坡 · 已签收', eta: '2026-11-15', createdAt: '2026-11-10', updatedAt: '2026-11-15 14:10',
    timeline: [
      event('delivered', '吉隆坡收货地址', '2026-11-15 14:10', '包裹已由收件人本人签收。'),
      event('delivery', '吉隆坡配送站', '2026-11-15 09:05', '包裹已安排当地配送。'),
      event('customs', '吉隆坡海关', '2026-11-14 13:40', '清关完成，包裹已放行。'),
      event('transit', '吉隆坡国际机场', '2026-11-13 18:15', '货物已抵达目的地机场。'),
      event('shipped', '广州白云机场', '2026-11-12 08:30', '包裹已交付航空承运商。'),
      event('warehouse', '广州集运仓', '2026-11-10 12:20', '包裹已完成入库及称重。'),
    ],
  }),
];

const cloneSamples = () => JSON.parse(JSON.stringify(SAMPLE_SHIPMENTS));
const isText = (value) => typeof value === 'string' && value.trim().length > 0;
const isStatus = (value) => Object.hasOwn(STATUS_PROGRESS, value);

function validShipment(shipment) {
  if (!shipment || typeof shipment !== 'object') return false;
  const place = (value) => value && ['city', 'country', 'code'].every((key) => isText(value[key]));
  return ['id', 'goods', 'method', 'location', 'eta', 'createdAt', 'updatedAt'].every((key) => isText(shipment[key]))
    && isStatus(shipment.status)
    && ['pieces', 'weight', 'volume', 'progress'].every((key) => Number.isFinite(shipment[key]) && shipment[key] >= 0)
    && place(shipment.origin) && place(shipment.destination)
    && shipment.recipient && ['name', 'phone', 'address'].every((key) => isText(shipment.recipient[key]))
    && Array.isArray(shipment.timeline) && shipment.timeline.length > 0
    && shipment.timeline.every((item) => item && isStatus(item.status)
      && ['title', 'description', 'location', 'time'].every((key) => isText(item[key])));
}

function defaultStorage() {
  try { return globalThis.localStorage; } catch { return undefined; }
}

export function authenticate(role, username, password) {
  if (!Object.hasOwn(DEMO_ACCOUNTS, role)) return null;
  const account = DEMO_ACCOUNTS[role];
  if (account.username !== username || account.password !== password) return null;
  return { role, name: role === 'admin' ? '运营管理员' : '林先生', username };
}

export function getShipments(storage = defaultStorage()) {
  try {
    const raw = storage?.getItem(STORAGE_KEY);
    if (raw) {
      const shipments = JSON.parse(raw);
      if (Array.isArray(shipments) && shipments.every(validShipment)) return shipments;
    }
  } catch { /* A demo remains usable if local storage is blocked or corrupt. */ }
  return cloneSamples();
}

export function saveShipments(shipments, storage = defaultStorage()) {
  try {
    if (!storage?.setItem || !Array.isArray(shipments) || !shipments.every(validShipment)) return false;
    storage.setItem(STORAGE_KEY, JSON.stringify(shipments));
    return true;
  } catch { return false; }
}

export function filterShipments(shipments, { query = '', status = 'all' } = {}) {
  const normalized = String(query).trim().toLocaleLowerCase();
  return shipments.filter((shipment) => {
    if (status !== 'all' && shipment.status !== status) return false;
    return !normalized || [shipment.id, shipment.goods, shipment.origin.city, shipment.destination.city, shipment.location]
      .some((value) => value.toLocaleLowerCase().includes(normalized));
  });
}

export function getStats(shipments) {
  return shipments.reduce((stats, { status }) => {
    stats.total += 1;
    if (status === 'warehouse') stats.warehouse += 1;
    else if (status === 'delivered') stats.delivered += 1;
    else if (['shipped', 'transit', 'customs', 'delivery'].includes(status)) stats.transit += 1;
    return stats;
  }, { total: 0, transit: 0, warehouse: 0, delivered: 0 });
}

function localTimestamp() {
  const now = new Date();
  const pad = (value) => String(value).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`;
}

export function updateShipment(shipments, id, { status, location, note }) {
  if (!isStatus(status)) throw new Error('请选择有效的运输状态');
  if (!isText(location)) throw new Error('请输入当前位置');
  if (!isText(note)) throw new Error('请输入轨迹说明');
  if (!shipments.some((shipment) => shipment.id === id)) throw new Error('未找到该运单');
  const updatedAt = localTimestamp();
  const nextLocation = location.trim();
  return shipments.map((shipment) => shipment.id === id ? {
    ...shipment, status, location: nextLocation, updatedAt, progress: STATUS_PROGRESS[status],
    timeline: [event(status, nextLocation, updatedAt, note.trim()), ...shipment.timeline],
  } : shipment);
}

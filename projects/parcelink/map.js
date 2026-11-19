const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));

// A deliberately simplified projection keeps the map useful without a map service.
const project = ([longitude, latitude]) => ({ x: (longitude - 90) * 27, y: (31 - latitude) * 15 });
const countryPath = (coordinates) => coordinates.map((coordinate, index) => {
  const { x, y } = project(coordinate);
  return `${index ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`;
}).join(' ') + ' Z';

const countries = [
  ['china', [[90, 34], [128, 34], [128, 31], [123, 31], [121.6, 30.8], [121.9, 29.9], [121.4, 28.9], [120.6, 28.2], [120.3, 27.1], [119.6, 26.2], [119, 25.6], [118.2, 24.6], [117.3, 23.9], [116.4, 23.1], [115.4, 22.8], [114.5, 22.5], [113.7, 22.7], [113.4, 22], [112.6, 21.7], [111.7, 21.5], [110.6, 21.2], [110.2, 20.4], [109.7, 20.3], [109.4, 21.3], [108.4, 21.7], [108, 21.5], [107, 21.5], [106.6, 22.1], [105.6, 22.7], [104.6, 22.8], [103.9, 22.6], [103.1, 22.4], [102.7, 22.9], [102, 22.5], [101.6, 21.1], [101.2, 21.7], [100, 22], [99.2, 22.2], [98.6, 23.7], [98, 24.8], [97.3, 25.4], [97.7, 26.6], [97.3, 27.8], [96, 28.2], [95, 29], [92, 28], [90, 28.1]]],
  ['myanmar', [[92, 28], [95, 29], [96, 28.2], [97.3, 27.8], [97.7, 26.6], [97.3, 25.4], [98, 24.8], [98.6, 23.7], [99.2, 22.2], [100, 22], [100.1, 20.9], [99.5, 20.3], [98.7, 20.1], [98.2, 18.7], [97.5, 18.1], [97.6, 16.9], [98.4, 16], [98.2, 14.9], [98.6, 13.8], [99.2, 12.6], [99.1, 11.7], [98.9, 10.6], [98.5, 10], [98.2, 11.8], [97.7, 13], [97.5, 14.6], [96.9, 15.8], [96.1, 16.5], [95.2, 15.8], [94.3, 16.1], [94.4, 17.2], [94.1, 18.2], [93.5, 19.2], [93.1, 20.2], [92.3, 21.5], [92.7, 22.7], [93.2, 24], [94.2, 25], [94.4, 26.5], [93.1, 27.2]]],
  ['laos', [[102, 22.5], [102.7, 22.9], [103.1, 22.4], [102.6, 21.2], [103.2, 20.1], [104.1, 19.2], [104.7, 18.1], [105.6, 17.2], [107, 15.7], [107.2, 14.6], [106.3, 14.4], [105.6, 15.6], [105.1, 16.1], [104.7, 17.5], [104, 18.2], [103.1, 18.4], [102, 18], [101.3, 18], [101.1, 19.6], [100.5, 19], [100.2, 19.7], [100.1, 20.9], [101.2, 21.7], [101.6, 21.1]]],
  ['thailand', [[98.7, 20.1], [99.5, 20.3], [100.2, 19.7], [100.5, 19], [101.1, 19.6], [101.3, 18], [102, 18], [103.1, 18.4], [104, 18.2], [104.7, 17.5], [105.1, 16.1], [105.6, 15.6], [105.1, 14.4], [103.1, 14.4], [102.5, 13.6], [102.9, 12.4], [102.1, 12], [101.4, 12.6], [100.9, 13.4], [100.5, 13.7], [100.1, 13.2], [99.9, 12.1], [99.7, 11.2], [99.3, 10.4], [99.5, 9.7], [99.9, 9.2], [100.2, 8.4], [100.5, 7.4], [101.1, 6.8], [102.1, 6.3], [101.1, 5.7], [100.1, 6.4], [99.6, 7.2], [99.2, 7.9], [98.5, 8.4], [98.3, 9], [98.5, 10], [98.9, 10.6], [99.1, 11.7], [99.2, 12.6], [98.6, 13.8], [98.2, 14.9], [98.4, 16], [97.6, 16.9], [97.5, 18.1], [98.2, 18.7]]],
  ['cambodia', [[103.1, 14.4], [105.1, 14.4], [105.6, 15.6], [106.3, 14.4], [107.2, 14.6], [107.5, 13.5], [107.4, 12.4], [106.1, 11.8], [105.9, 10.9], [104.9, 10.4], [103.8, 10.5], [103.2, 11.2], [102.9, 12.4], [102.5, 13.6]]],
  ['vietnam', [[102.1, 22.4], [103.1, 22.4], [104, 22.6], [105.6, 22.7], [106.6, 22.1], [107, 21.5], [108, 21.5], [107.6, 20.8], [106.3, 20.5], [105.8, 19.8], [105.6, 18.9], [106.4, 17.7], [107.3, 16.7], [108.2, 16.1], [108.7, 15.4], [109.1, 13.8], [109.4, 12.5], [109.2, 11.4], [108.5, 10.7], [107.4, 10.4], [106.7, 10.3], [105.9, 9.4], [105, 8.6], [104.7, 9], [104.9, 10.4], [105.9, 10.9], [106.1, 11.8], [107.4, 12.4], [107.5, 13.5], [107.2, 14.6], [107, 15.7], [105.6, 17.2], [104.7, 18.1], [104.1, 19.2], [103.2, 20.1], [102.6, 21.2]]],
  ['malaysia', [[100.1, 6.4], [101.1, 5.7], [102.1, 6.3], [102.5, 5.1], [103.3, 4.5], [103.4, 3.5], [103.5, 2.7], [104.1, 1.6], [103.6, 1.3], [102.9, 1.7], [102.1, 2.2], [101.4, 2.9], [100.8, 3.7], [100.4, 4.3], [100.1, 5.2]]],
  ['sumatra', [[95.3, 5.9], [96.2, 5.5], [97.1, 5.2], [98, 4.5], [98.7, 3.6], [99.8, 2.3], [100.8, 1.8], [101.6, 1.6], [102.6, .8], [103.3, -.8], [104.5, -2.3], [105.9, -4.7], [105.6, -5.9], [104.6, -5.5], [103.7, -4.7], [102.2, -3.4], [101.3, -2.3], [100.2, -.8], [99.4, .6], [98.3, 1.8], [97.5, 2.5], [96.7, 3.8], [95.7, 4.5]]],
  ['borneo', [[109, 2], [109.5, 1.3], [110.5, 1.1], [111.4, 1.6], [112.4, 1.6], [113.2, 2.6], [113.9, 3.3], [114.6, 4.1], [115.2, 4.5], [115.6, 5.4], [116.4, 6.2], [117.2, 7], [117.5, 6.2], [118.3, 5.6], [119, 5.2], [118.5, 4.4], [117.9, 4], [118.2, 3.1], [117.6, 2.3], [117.9, 1.2], [117.4, .6], [117.7, -.8], [116.6, -2], [116.3, -3.4], [114.7, -4.1], [113.8, -3.3], [112.9, -3], [111.8, -3.2], [111, -2.8], [110.1, -1.2], [109.4, -.8], [109.1, .2]]],
  ['hainan', [[108.7, 19.9], [109.4, 20.1], [110.3, 20], [110.9, 19.5], [110.5, 18.7], [109.8, 18.2], [109.2, 18.3], [108.7, 19]]],
  ['taiwan', [[121.6, 25.3], [121.9, 24.7], [121.5, 23.5], [120.9, 22.1], [120.5, 22.5], [120.2, 23.7], [120.6, 24.6]]],
  ['palawan', [[119.3, 11.4], [119.6, 10.8], [118.9, 9.7], [118.5, 9.2], [117.6, 8.4], [118, 9.4], [118.6, 10.3]]],
  ['luzon', [[120.6, 18.6], [121.5, 18.4], [122.2, 18], [122.1, 16.8], [121.5, 16], [121.9, 14.7], [123.2, 13.3], [122.5, 13.6], [121.4, 14.2], [120.6, 14.5], [120.1, 15.6], [120.4, 16.6]]],
];

const airports = {
  SZX: project([114.06, 22.55]),
  CAN: project([113.26, 23.13]),
  YIW: project([120.08, 29.31]),
  KUL: project([101.69, 3.14]),
  SIN: project([103.82, 1.35]),
  BKK: project([100.5, 13.76]),
};

const interpolate = (a, b, t) => ({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t });
const cubicPath = ([a, b, c, d]) => `M${a.x.toFixed(2)},${a.y.toFixed(2)} C${b.x.toFixed(2)},${b.y.toFixed(2)} ${c.x.toFixed(2)},${c.y.toFixed(2)} ${d.x.toFixed(2)},${d.y.toFixed(2)}`;

function splitRoute(points, progress) {
  const [a, b, c, d] = points;
  const ab = interpolate(a, b, progress);
  const bc = interpolate(b, c, progress);
  const cd = interpolate(c, d, progress);
  const abc = interpolate(ab, bc, progress);
  const bcd = interpolate(bc, cd, progress);
  const current = interpolate(abc, bcd, progress);
  return { traveled: cubicPath([a, ab, abc, current]), remaining: cubicPath([current, bcd, cd, d]), current };
}

function transportIcon(method, size = 20) {
  const isAir = /air|空|航班/i.test(method);
  const isRoad = /road|truck|陆|汽运/i.test(method);
  const shape = isAir
    ? '<path d="m3 11 6.5 1.8L12 21l2-1 1-7 5-5c1.3-1.3.8-2.8-.2-3.8S17.3 2.7 16 4l-5 5-7 1-1 2Z"/><path d="m10 8-1-5 2-1 4 5M16 14l5 1 1-2-5-4"/>'
    : isRoad
      ? '<path d="M3 6h11v11H3zM14 10h4l3 4v3h-7"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/>'
      : '<path d="M4 13v-5h5V4h6v4h5v5M2 14l10-3 10 3-4 6H6l-4-6Z"/><path d="M7 8h10M12 4v7M3 22c1.5-1 3-1 4.5 0 1.5-1 3-1 4.5 0 1.5-1 3-1 4.5 0 1.5-1 3-1 4.5 0"/>';
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${shape}</svg>`;
}

function cityLabel(point, city, code, isDestination = false) {
  const x = point.x + 13;
  const y = point.y + (isDestination ? 22 : -14);
  return `<g class="map-endpoint-label"><text x="${x}" y="${y}" class="map-city-name">${escapeHTML(city)}</text><text x="${x}" y="${y + 15}" class="map-city-code">${escapeHTML(code)}</text></g>`;
}

export function renderRouteMap(shipment = {}) {
  const origin = shipment.origin || { city: '深圳', code: 'SZX' };
  const destination = shipment.destination || { city: '吉隆坡', code: 'KUL' };
  const start = airports[origin.code] || airports.SZX;
  const end = airports[destination.code] || airports.KUL;
  const isDelivered = /delivered|signed|已签收|已送达/i.test(String(shipment.status));
  const progress = isDelivered ? 100 : Math.round(Math.max(0, Math.min(100, Number(shipment.progress) || 0)));
  const method = String(shipment.method || '海运');
  const methodLabel = /air|空|航班/i.test(method) ? '空运' : /road|truck|陆|汽运/i.test(method) ? '陆运' : '海运';
  const location = shipment.location || origin.city || '起运地';
  const routeId = 'route-' + String(shipment.id || 'demo').replace(/[^a-zA-Z0-9_-]/g, '');
  const controls = destination.code === 'BKK'
    ? [{ x: start.x - 30, y: start.y + 110 }, { x: end.x + 110, y: end.y - 80 }]
    : [{ x: start.x + 36, y: start.y + 178 }, { x: end.x + 165, y: end.y - 70 }];
  const points = [start, ...controls, end];
  const { traveled, remaining, current } = splitRoute(points, progress / 100);
  const icon = transportIcon(method);
  const countryShapes = countries.map(([name, coordinates]) => `<path class="map-land map-land--${name}" d="${countryPath(coordinates)}"/>`).join('');
  const graticule = [240, 375, 510, 645, 780, 915].map(x => `<path d="M${x} 0V530"/>`).join('') + [60, 135, 210, 285, 360, 435, 510].map(y => `<path d="M120 ${y}H950"/>`).join('');

  return `<div class="route-map" data-map-shipment="${escapeHTML(shipment.id)}">
    <svg class="map-illustration" viewBox="150 0 770 520" preserveAspectRatio="xMidYMid meet" role="img" aria-labelledby="${routeId}-title ${routeId}-desc">
      <title id="${routeId}-title">${escapeHTML(origin.city)}至${escapeHTML(destination.city)}运输路线示意</title>
      <desc id="${routeId}-desc">演示路线已完成${progress}%，当前位置：${escapeHTML(location)}。此地图为路线示意，非实时 GPS。</desc>
      <defs>
        <linearGradient id="${routeId}-water" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#edf3f7"/><stop offset="1" stop-color="#e6eff5"/></linearGradient>
        <filter id="${routeId}-shadow" x="-80%" y="-80%" width="260%" height="260%"><feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="#2354a3" flood-opacity=".18"/></filter>
        <pattern id="${routeId}-dots" width="14" height="14" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".7" fill="#c6d6e3" opacity=".23"/></pattern>
      </defs>
      <rect x="100" y="-30" width="900" height="590" fill="url(#${routeId}-water)"/>
      <rect x="100" y="-30" width="900" height="590" fill="url(#${routeId}-dots)"/>
      <g class="map-graticule">${graticule}</g>
      <g class="map-countries">${countryShapes}</g>
      <g class="map-inland-lines"><path d="M500 0 518 42 562 64 572 95 612 106"/><path d="M673 0 654 27 671 56 706 82 723 112"/><path d="M378 92 402 110 406 135 428 145"/></g>
      <g class="map-country-labels"><text x="603" y="50" class="map-country-label map-country-label--china">中 国</text><text x="194" y="195">缅甸</text><text x="296" y="223">泰国</text><text x="361" y="167">老挝</text><text x="396" y="282">柬埔寨</text><text x="491" y="247" transform="rotate(29 491 247)">越南</text><text x="285" y="393" class="map-small-country-label">马来西亚</text><text x="636" y="466">印 度 尼 西 亚</text><text x="805" y="247">菲律宾</text><text x="845" y="114" class="map-small-country-label">中国台湾</text></g>
      <g class="map-city-labels"><circle cx="427" cy="149" r="2"/><text x="438" y="153">河内</text><circle cx="452" cy="304" r="2"/><text x="464" y="308">胡志明市</text><circle cx="297" cy="314" r="2"/><text x="267" y="328">普吉岛</text><circle cx="608" cy="98" r="2"/><text x="570" y="92">广州</text></g>
      <g class="map-sea-label"><text x="677" y="294">南 海</text><text x="679" y="313" class="map-sea-label-en">SOUTH CHINA SEA</text></g>
      <path d="${cubicPath(points)}" class="map-route-halo"/>
      ${progress < 100 ? `<path d="${remaining}" class="map-route-remaining"/>` : ''}
      ${progress > 0 ? `<path d="${traveled}" class="map-route-traveled"/>` : ''}
      <circle cx="${start.x}" cy="${start.y}" r="7" class="map-origin-ring"/><circle cx="${start.x}" cy="${start.y}" r="3" class="map-origin-core"/>
      <circle cx="${end.x}" cy="${end.y}" r="7" class="map-destination-ring"/><circle cx="${end.x}" cy="${end.y}" r="2.5" class="map-destination-core"/>
      ${cityLabel(start, origin.city, origin.code)}${cityLabel(end, destination.city, destination.code, true)}
      <g class="map-position" transform="translate(${current.x.toFixed(2)} ${current.y.toFixed(2)})">
        <circle r="30" class="map-position-aura"/><circle r="24" class="map-position-pulse"/>
        <circle r="18" class="map-position-disc" filter="url(#${routeId}-shadow)"/>
        <g transform="translate(-10 -10)" class="map-position-icon">${icon}</g>
      </g>
    </svg>
    <div class="map-location-card">
      <span class="map-location-symbol">${icon}</span>
      <div class="map-location-copy"><span class="map-location-eyebrow">${isDelivered ? '送达位置' : '当前位置'}</span><strong title="${escapeHTML(location)}">${escapeHTML(location)}</strong><span class="map-location-detail">${methodLabel}<i></i>已完成 ${progress}%</span></div>
      <span class="map-location-dot" aria-hidden="true"></span>
    </div>
    <div class="map-north" aria-hidden="true"><span>N</span><svg viewBox="0 0 16 24" width="13" height="20"><path d="m8 1 6 19-6-4-6 4L8 1Z" fill="#72869a"/><path d="M8 1v15l-6 4L8 1Z" fill="#b2c0cd"/></svg></div>
    <div class="map-legend" aria-label="路线图例"><span><i class="map-legend-traveled"></i>已行驶路线</span><span><i class="map-legend-remaining"></i>预计路线</span></div>
    <span class="map-disclaimer">路线示意 · 非实时 GPS</span>
    <div class="map-controls" aria-label="地图缩放"><button type="button" data-action="map-zoom-in" aria-label="放大地图"><svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M10 4v12M4 10h12"/></svg></button><button type="button" data-action="map-zoom-out" aria-label="缩小地图"><svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M4 10h12"/></svg></button></div>
  </div>`;
}

import { STATUS_OPTIONS, DEMO_ACCOUNTS, authenticate, getShipments, filterShipments, getStats, updateShipment } from './data.js';
import { renderRouteMap } from './map.js';
import { deliveryDate, validTrackingNumber } from './shipment-view.js';
import { createApi } from './api.js';
import { SITE_CONFIG, normalizeSiteConfig } from './site-config.js';

const app = document.querySelector('#app');
const modalRoot = document.querySelector('#modal-root');
const escape = (value = '') => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const paths = {
  box:'<path d="m21 8-9 5-9-5M12 13v9M3 8l9-5 9 5v10l-9 5-9-5z"/><path d="m7.5 5.5 9 5"/>',
  grid:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  truck:'<path d="M3 6h11v12H3zM14 10h4l3 4v4h-7"/><circle cx="7" cy="18" r="2"/><circle cx="18" cy="18" r="2"/>',
  pin:'<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
  help:'<circle cx="12" cy="12" r="9"/><path d="M9.5 8.5a2.6 2.6 0 0 1 5 1c0 2-2.5 2-2.5 4M12 17h.01"/>',
  arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',
  chevron:'<path d="m9 5 7 7-7 7"/>',
  down:'<path d="m6 9 6 6 6-6"/>',
  plus:'<path d="M12 5v14M5 12h14"/>',
  search:'<circle cx="10.5" cy="10.5" r="7"/><path d="m16 16 4.5 4.5"/>',
  check:'<path d="m5 12 4 4L19 6"/>',
  shield:'<path d="m12 3 8 3v5c0 5-8 10-8 10s-8-5-8-10V6z"/><path d="m8 12 3 3 5-6"/>',
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  ship:'<path d="M7 10V4h10v6M12 4V1M3 13l9-4 9 4-3 7H6zM2 22q2-2 4 0t4 0 4 0 4 0 4 0"/><path d="M12 9v10"/>',
  plane:'<path d="m22 2-8 20-4-8-8-4zM22 2 10 14"/>',
  logout:'<path d="M9 4H4v16h5M14 8l4 4-4 4M8 12h13"/>',
  bell:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
  copy:'<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
  close:'<path d="m6 6 12 12M6 18 18 6"/>',
  user:'<circle cx="12" cy="8" r="4"/><path d="M4 22v-2a8 8 0 0 1 16 0v2"/>',
  lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4M12 14v3"/>',
  eye:'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 2v6M17 2v6M3 11h18"/>',
  support:'<path d="M3 14v-3a9 9 0 0 1 18 0v6c0 3-4 4-8 4"/><rect x="2" y="11" width="4" height="7" rx="2"/><rect x="18" y="11" width="4" height="7" rx="2"/>',
  external:'<path d="M14 3h7v7M21 3 10 14M10 3H3v18h18v-7"/>',
  warehouse:'<path d="m3 10 9-7 9 7v11H3zM8 21V11h8v10M8 15h8M8 18h8"/>',
  edit:'<path d="m16 3 5 5-12 12-6 1 1-6zM14 5l5 5"/>',
  globe:'<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
  download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  mail:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 6 9 7 9-7"/>',
};
const icon = (name, size = 20) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.box}</svg>`;
const statusOf = s => STATUS_OPTIONS.find(o => o.id === s.status) || STATUS_OPTIONS[0];
const badge = s => `<span class="status-badge ${statusOf(s).color}"><i></i>${escape(statusOf(s).label)}</span>`;
const logo = () => `<span class="brand-icon">${icon('box',25)}</span><span class="brand-name">集运通<small>PARCELINK</small></span>`;
const demoMode = new URLSearchParams(window.location.search).get('demo') === '1';
const api = createApi();
let siteConfig = normalizeSiteConfig(SITE_CONFIG);
let shipments = demoMode ? getShipments(null) : [];
let session = null;
let page = 'overview', filter = 'all', query = '', selectedId = shipments[0]?.id;
let loginRole = 'customer', expandedTimeline = false, zoom = 1;
let lastModalFocus = null, initializing = !demoMode, loginError = '', connectionError = '', configError = '';
let lastSynced = null, nextPage = null, totalShipments = shipments.length, refreshing = false;
let refreshTimer = null, sessionVersion = 0, shipmentRequest = null;
const disclosureState = new Map();
let renderedConnectionBanner = '';
function rememberDisclosures() {
  app.querySelectorAll('details[data-disclosure]').forEach(element => disclosureState.set(element.dataset.disclosure,element.open));
}
function disclosureAttributes(key, initiallyOpen = false) {
  return `data-disclosure="${escape(key)}" ${(disclosureState.get(key) ?? initiallyOpen) ? 'open' : ''}`;
}
const weightLabel = shipment => shipment.weight === null ? '待称重' : `${shipment.weight} kg`;
const volumeLabel = shipment => shipment.volume === null ? '体积待确认' : `${shipment.volume} m³`;
const avatarText = () => escape(session?.role === 'admin' ? '管' : (session?.name || session?.username || '客').slice(0,1));
const eventKey = () => crypto.randomUUID ? crypto.randomUUID() : Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2,'0')).join('');

function contactLinks() {
  const {phone,email} = siteConfig.company;
  const placeholderPhone = siteConfig.company.isPlaceholder || phone === '000-00000000', placeholderEmail = siteConfig.company.isPlaceholder || email === 'support@example.com';
  return `<span class="company-contact">电话：${phone ? placeholderPhone ? `${escape(phone)} <small>（占位）</small>` : `<a href="tel:${escape(phone.replace(/[^+\d]/g,''))}">${escape(phone)}</a>` : '<span class="unconfigured">待配置</span>'}</span><span class="company-contact">邮箱：${email ? placeholderEmail ? `${escape(email)} <small>（占位）</small>` : `<a href="mailto:${escape(email)}">${escape(email)}</a>` : '<span class="unconfigured">待配置</span>'}</span>${placeholderPhone || placeholderEmail ? '<span class="contact-placeholder-note">占位联系方式，正式服务信息待配置</span>' : ''}`;
}

function accessLinks(key = 'access') {
  const {primaryDomain,backupDomains} = siteConfig.access;
  const links = [[primaryDomain,'主访问地址'], ...backupDomains.map((url,i)=>[url,`备用地址 ${i+1}`])].filter(([url])=>url);
  return `<details class="access-panel" ${disclosureAttributes(key)}><summary>${icon('globe',15)} 访问地址与备用入口 ${icon('down',13)}</summary><div class="access-panel-body">${links.length ? links.map(([url,label])=>`<div class="access-row"><span>${label}</span><a href="${escape(url)}" target="_blank" rel="noopener noreferrer">${escape(url)} ${icon('external',12)}</a><button class="icon-button" data-action="copy-access" data-url="${escape(url)}" aria-label="复制${label}">${icon('copy',14)}</button></div>`).join('') : '<p>主域名与备用域名待配置。</p>'}<p>切换地址后请重新登录。备用入口仅在此页面已加载时可用；若主站完全无法打开，请使用提前收藏的备用地址。</p></div></details>`;
}

function connectionBanner() {
  const message = connectionError || configError;
  return message ? `<section class="connection-banner" role="alert"><div>${icon('help',18)}<span>${escape(message)}${session && lastSynced ? ' 当前保留上次成功读取的运单。' : ''}</span><button class="text-button" data-action="retry-connection" ${refreshing?'disabled':''}>重试</button></div>${accessLinks('connection-access')}</section>` : '';
}

function syncStatus() {
  return `<div class="sync-status"><span>${icon('clock',13)} ${demoMode ? '静态展示 · 修改仅本页有效' : `${refreshing?'正在读取 · ':''}最近同步 ${lastSynced ? lastSynced.toLocaleTimeString('zh-CN',{hour12:false}) : '尚未同步'} · 页面可见时每 30 秒刷新`}</span>${!demoMode?`<button class="text-button" data-action="refresh-shipments" ${refreshing?'disabled':''}>${refreshing?'刷新中…':'刷新运单'}</button>`:''}</div>`;
}

function stopPolling() { if (refreshTimer) clearInterval(refreshTimer); refreshTimer = null; }
function startPolling() {
  stopPolling();
  if (!demoMode && session) refreshTimer = setInterval(()=>{ if (document.visibilityState === 'visible' && !modalRoot.innerHTML) refreshShipments(); },30000);
}

function clearSession(message = '') {
  sessionVersion += 1;
  stopPolling();
  session = null;
  shipments = demoMode ? getShipments(null) : [];
  totalShipments = shipments.length;
  nextPage = null;
  lastSynced = null;
  connectionError = '';
  loginError = message;
  refreshing = false;
  closeModal();
  render();
}

function acceptUser(user) {
  if (!user || !['customer','admin'].includes(user.role)) throw new Error('服务器返回了无效的账户信息。');
  sessionVersion += 1;
  session = user;
  page='overview'; filter='all'; query=''; loginError=''; connectionError='';
  if (!demoMode) { shipments=[]; totalShipments=0; nextPage=null; }
  render();
  startPolling();
}

async function refreshShipments(options = {}) {
  if (!session || demoMode) return false;
  if (shipmentRequest?.version === sessionVersion) return shipmentRequest.promise;
  const request = {version:sessionVersion,promise:null};
  shipmentRequest = request;
  request.promise = loadShipments(options);
  try {return await request.promise;} finally {if(shipmentRequest===request)shipmentRequest=null;}
}

async function loadShipments({append=false} = {}) {
  const version = sessionVersion;
  refreshing = true;
  let dataChanged = false;
  refreshVisibleShipmentPanels();
  try {
    const data = await api.shipments(append && nextPage ? nextPage : undefined);
    const targetCount = Math.max(100,shipments.length), seenPages = new Set();
    // Keep already loaded pages available when a background refresh runs.
    while (!append && data.next && data.results.length < targetCount) {
      if(seenPages.has(data.next))throw new Error('服务器返回了重复的分页地址，请稍后重试。');
      seenPages.add(data.next);
      const more = await api.shipments(data.next);
      if(version !== sessionVersion)return false;
      data.results.push(...more.results); data.next=more.next; data.count=more.count;
    }
    if (version !== sessionVersion) return false;
    const nextShipments = append ? [...new Map([...shipments,...data.results].map(item=>[item.id,item])).values()] : data.results;
    dataChanged = JSON.stringify(nextShipments)!==JSON.stringify(shipments) || totalShipments!==data.count || nextPage!==(data.next || null);
    shipments = nextShipments;
    totalShipments = data.count; nextPage = data.next || null;
    lastSynced = new Date(); connectionError='';
    return true;
  } catch (error) {
    if (version !== sessionVersion) return false;
    if (error.status === 401) { clearSession('登录已过期，请重新登录。'); return false; }
    connectionError = error.message;
    return false;
  } finally {
    if (version === sessionVersion) { refreshing = false; refreshVisibleShipmentPanels(dataChanged); }
  }
}

async function loadConfig() {
  try {
    const data = await api.publicConfig();
    siteConfig = normalizeSiteConfig({company:{...SITE_CONFIG.company,...data.company},access:{...SITE_CONFIG.access,...data.access}});
    configError = '';
  } catch (error) { configError = `公司与访问地址配置暂时无法读取：${error.message}`; }
}

async function initialize() {
  if (demoMode) return render();
  render();
  const results = await Promise.allSettled([loadConfig(),api.me()]);
  initializing = false;
  const account = results[1];
  if (account.status === 'fulfilled') {
    try { acceptUser(account.value.user); await refreshShipments(); }
    catch(error) { clearSession(error.message); }
  } else {
    connectionError = account.reason.status !== 401 ? account.reason.message : '';
    render();
  }
}

function toast(message) {
  const el = document.createElement('div'); el.className = 'toast'; el.setAttribute('role','status');
  el.innerHTML = `${icon('check',18)}<span>${escape(message)}</span>`;
  document.querySelector('#toast-root').append(el);
  setTimeout(() => el.remove(), 3600);
}

function renderLogin() {
  rememberDisclosures();
  app.innerHTML = `<div class="login-page"><header class="login-header"><a class="brand" href="./" aria-label="集运通首页">${logo()}</a><span class="login-environment"><i></i> ${demoMode?'静态展示环境':'客户服务平台'}</span></header>
    <main class="login-layout"><section class="login-story"><div class="story-eyebrow"><span></span> CONNECTING YOUR WORLD</div><h1>跨越山海，<br>每一程都<span>心中有数。</span></h1><p>从仓库到家门，物流轨迹一目了然。<br>让全球集运，变得简单一点。</p>
      <div class="login-globe" aria-hidden="true"><svg viewBox="0 0 620 390"><defs><radialGradient id="glow"><stop stop-color="#325cae" stop-opacity=".55"/><stop offset="1" stop-color="#182d56" stop-opacity="0"/></radialGradient></defs><circle cx="330" cy="225" r="220" fill="url(#glow)"/><g fill="none" stroke="#7198df" stroke-opacity=".2"><ellipse cx="330" cy="225" rx="250" ry="142" transform="rotate(-20 330 225)"/><ellipse cx="330" cy="225" rx="250" ry="80" transform="rotate(-20 330 225)"/><ellipse cx="330" cy="225" rx="160" ry="142" transform="rotate(-20 330 225)"/><ellipse cx="330" cy="225" rx="70" ry="142" transform="rotate(-20 330 225)"/><path d="M82 225h496M105 155h440M130 315h400"/></g><path d="M155 245Q280 70 490 180" fill="none" stroke="#76a4ff" stroke-width="2" stroke-dasharray="5 6"/><path d="M155 245Q250 112 356 136" fill="none" stroke="#83b8ff" stroke-width="3"/><g fill="#8fb9ff"><circle cx="155" cy="245" r="5"/><circle cx="490" cy="180" r="5"/></g><circle cx="356" cy="136" r="18" fill="#3876ea"/><path d="m347 135 18-7-7 18-3-8z" fill="white"/><text x="130" y="271" fill="#c5d6f7" font-size="13">深圳 SZX</text><text x="455" y="207" fill="#c5d6f7" font-size="13">吉隆坡 KUL</text></svg><div class="floating-shipment"><span class="floating-icon">${icon('ship',22)}</span><div><strong>您的包裹，正在靠近</strong><span><i></i> 专线运输 · 路线示意</span></div>${icon('arrow',19)}</div></div>
      <div class="login-story-footer"><span>${icon('shield',17)} 安心集运</span><span>${icon('globe',17)} 全球连接</span><span>${icon('pin',17)} 轨迹透明</span></div></section>
    <section class="login-form-side"><div class="login-form-wrap"><span class="tiny-label">WELCOME TO PARCELINK</span><h2>欢迎回来</h2><p class="login-intro">登录您的账户，查看包裹的最新旅程。</p><div class="role-tabs" aria-label="选择登录角色"><button class="${loginRole==='customer'?'active':''}" data-action="login-role" data-role="customer">${icon('user',17)} 客户登录</button><button class="${loginRole==='admin'?'active':''}" data-action="login-role" data-role="admin">${icon('shield',17)} 管理员登录</button></div>
      <form id="login-form"><label for="username">${loginRole==='customer'?'客户账号':'管理员账号'}</label><div class="input-with-icon">${icon('user',19)}<input id="username" name="username" autocomplete="username" value="" ${initializing?'disabled':''} placeholder="请输入账号" required></div><label for="password">登录密码</label><div class="input-with-icon">${icon('lock',19)}<input id="password" name="password" type="password" autocomplete="current-password" value="" ${initializing?'disabled':''} placeholder="请输入密码" required><button class="icon-button" type="button" data-action="toggle-password" aria-label="显示或隐藏密码">${icon('eye',18)}</button></div><div class="login-options"><label class="checkbox-label"><input name="remember" type="checkbox" checked> 记住登录状态</label><button type="button" class="text-button" data-action="login-help">登录遇到问题？</button></div><p class="form-error" id="login-error" role="alert">${escape(loginError)}</p><button type="submit" class="button primary login-submit" ${initializing?'disabled':''}>${initializing?'正在检查登录状态…':'登录'}${icon('arrow',18)}</button></form>
      ${demoMode?`<div class="demo-separator"><span></span> 想先了解一下？ <span></span></div><button class="button demo-login" data-action="demo-login">${icon('external',17)}一键体验${loginRole==='customer'?'客户':'管理员'}演示</button><div class="demo-account">演示账号 <code>${loginRole==='customer'?'demo':'admin'}</code><span>密码 <code>123456</code></span></div>`:''}<p class="login-disclaimer">${icon('shield',14)} ${demoMode?'静态展示不连接业务服务器，刷新后恢复示例数据。':'使用公司分配的账号登录，账户权限由服务器验证。'}</p>${connectionBanner()}<div class="login-contacts">${contactLinks()}</div>${accessLinks()}</div></section></main><footer class="login-footer"><span>© ${new Date().getFullYear()} ${escape(siteConfig.company.name)}</span><span>每一程，心中有数。</span></footer></div>`;
}

function sidebar() {
  const nav = [['overview','grid','物流总览'],['shipments','box',session.role==='admin'?'运单管理':'我的运单'],['addresses','warehouse','仓库地址'],['help','help','帮助中心']];
  return `<aside class="sidebar"><a href="./" class="brand sidebar-brand">${logo()}</a><div class="workspace-label">${session.role==='admin'?'运营工作台':'客户工作台'} ${demoMode?'<span>DEMO</span>':''}</div><nav aria-label="主要导航">${nav.map(([id,ico,label])=>`<button class="nav-item ${page===id?'active':''}" data-action="nav" data-page="${id}" aria-label="${label}">${icon(ico,20)}<span>${label}</span>${id==='shipments'?`<small>${shipments.length}</small>`:''}</button>`).join('')}${session.role==='admin'&&!demoMode?`<a class="nav-item" href="/admin/" target="_blank" rel="noopener" aria-label="后台管理（新窗口打开）" title="后台管理">${icon('shield',20)}<span>后台管理</span>${icon('external',14)}</a>`:''}</nav><div class="sidebar-bottom"><div class="support-card"><span class="support-icon">${icon('support',22)}</span><strong>每一步，我们都在</strong><p>集运遇到问题？随时联系我们</p><button data-action="support">联系客服 ${icon('arrow',15)}</button></div><div class="sidebar-user"><span class="avatar">${avatarText()}</span><div><strong>${escape(session.name)}</strong><span>${session.role==='admin'?'运营管理员':`客户 · ${escape(session.customerCode || '会员编号待分配')}`}</span></div><button class="icon-button" data-action="logout" aria-label="退出登录" title="退出登录">${icon('logout',18)}</button></div></div></aside>`;
}

function render() {
  if (!session) return renderLogin();
  rememberDisclosures();
  const connectionMarkup = connectionBanner();
  const activeInput = document.activeElement?.id === 'shipment-search' ? {start:document.activeElement.selectionStart,end:document.activeElement.selectionEnd} : null;
  const labels = {overview:'物流总览',shipments:session.role==='admin'?'运单管理':'我的运单',addresses:'仓库地址',help:'帮助中心'};
  app.innerHTML = `${sidebar()}<div class="app-main"><header class="topbar"><div class="breadcrumb">工作台 ${icon('chevron',13)} <span>${labels[page]}</span></div><div class="topbar-actions"><span class="demo-badge"><i></i> ${demoMode?'静态展示':'共享运单'}</span><button class="notification-button icon-button" data-action="notifications" aria-label="查看通知">${icon('bell',20)}<i></i></button><span class="topbar-divider"></span><span class="avatar small">${avatarText()}</span><span class="topbar-name">${escape(session.name)}</span></div></header><main class="content" id="main-content"><div id="connection-status">${connectionMarkup}</div>${page==='addresses'?addressesPage():page==='help'?helpPage():dashboard()}</main><footer class="app-footer"><span>© ${new Date().getFullYear()} ${escape(siteConfig.company.name)} · 每一程，心中有数</span><div class="footer-contacts">${contactLinks()}</div><span><i></i> ${demoMode?'示例数据 · ':''}路线示意，非实时定位</span></footer></div>`;
  renderedConnectionBanner = JSON.stringify([connectionError || configError,Boolean(session && lastSynced)]);
  if (activeInput) {const input=document.querySelector('#shipment-search');input?.focus();input?.setSelectionRange(activeInput.start,activeInput.end);}
}

function dashboard() {
  const stats = getStats(shipments);
  return `<section class="page-heading"><div><div class="eyebrow">YOUR SHIPMENTS, AT A GLANCE</div><h1>${page==='overview'?'物流总览':session.role==='admin'?'运单管理':'我的运单'}<span class="heading-dot">.</span></h1><p>从入库到签收，每一步都清晰可见。</p></div><div class="heading-actions"><span class="today">${icon('calendar',16)} ${new Date().toLocaleDateString('zh-CN')} ${demoMode?'<small>演示</small>':''}</span>${session.role==='customer'?`<button class="button primary" data-action="new-shipment">${icon('plus',17)} 新增包裹预报</button>`:''}</div></section>
    ${session.role==='admin'?`<div class="admin-banner">${icon('shield',19)}<span><strong>管理员工作台</strong> ${demoMode?'当前为静态展示，操作仅保留在本页。':'选择运单可更新轨迹；后台管理支持客户、运单及预报管理。'}</span></div>`:''}
    ${syncStatus()}<section class="stats-grid" aria-label="运单统计">${[
      ['全部运单',stats.total,'box','blue','all','所有旅程，尽在掌握'],['运输途中',stats.transit,'truck','violet','moving','正在向您靠近'],['仓库待出库',stats.warehouse,'warehouse','amber','warehouse','已安全抵达仓库'],['已签收',stats.delivered,'check','green','delivered','美好已经送达']
    ].map(([label,n,ico,color,f,sub])=>`<button class="stat-card ${filter===f?'stat-selected':''}" data-action="filter" data-filter="${f}"><div class="stat-top"><span>${label}</span><span class="stat-icon ${color}">${icon(ico,20)}</span></div><div class="stat-number">${n}<small>票</small></div><div class="stat-note">${color==='green'?'<i class="green-dot"></i>':''}${sub}${icon('chevron',13)}</div></button>`).join('')}</section>
    <section class="tracking-section"><div class="section-heading"><div><h2>${session.role==='admin'?'运单列表':'我的运单'} <span>${shipments.length}</span></h2><p>追踪每个包裹的下一站${nextPage?` · 已读取 ${shipments.length} / ${totalShipments} 票，搜索与统计基于已加载运单`:''}</p></div><div class="search-box">${icon('search',18)}<input id="shipment-search" aria-label="搜索运单号、物品或目的地" placeholder="搜索运单号、物品或目的地" value="${escape(query)}">${query?'<button class="icon-button" data-action="clear-search" aria-label="清空搜索">'+icon('close',15)+'</button>':''}</div></div><div class="filter-bar" role="group" aria-label="运单状态筛选">${[['all','全部运单'],['moving','运输中'],['warehouse','待出库'],['delivered','已签收']].map(([id,label])=>`<button class="filter-tab ${filter===id?'active':''}" data-action="filter" data-filter="${id}">${label}${id==='all'?`<span>${shipments.length}</span>`:''}</button>`).join('')}<span class="filter-hint">${icon('clock',13)} 最近更新 ${escape(shipments.map(s=>s.updatedAt).sort().at(-1)?.slice(5) || '暂无')}</span></div><div class="tracking-workspace" id="tracking-workspace">${workspace()}</div></section>
    <div class="trust-strip"><span>${icon('shield',17)} 包裹妥善保管</span><span>${icon('globe',17)} 专业跨境专线</span><span>${icon('support',17)} 专属客服支持</span><span class="trust-tag">一路相伴，安心抵达 ${icon('arrow',16)}</span></div>`;
}

function refreshVisibleShipmentPanels(dataChanged = false) {
  if (!session) return;
  const signature = JSON.stringify([connectionError || configError,Boolean(session && lastSynced)]);
  if (signature !== renderedConnectionBanner) {
    rememberDisclosures();
    const slot = document.querySelector('#connection-status');
    if (slot) slot.innerHTML = connectionBanner();
    renderedConnectionBanner = JSON.stringify([connectionError || configError,Boolean(session && lastSynced)]);
  }
  // Background reads continue on help/warehouse pages without replacing their DOM.
  if (!['overview','shipments'].includes(page)) return;
  const sync = app.querySelector('.sync-status');
  if (sync) sync.outerHTML = syncStatus();
  if (!dataChanged) return;
  const stats = getStats(shipments);
  app.querySelectorAll('.stats-grid .stat-number').forEach((element,i)=>{
    element.innerHTML = `${[stats.total,stats.transit,stats.warehouse,stats.delivered][i]}<small>票</small>`;
  });
  for (const selector of ['.section-heading h2>span','.filter-tab[data-filter="all"]>span','.nav-item[data-page="shipments"]>small']) {
    const count = app.querySelector(selector); if(count)count.textContent=String(shipments.length);
  }
  const description=app.querySelector('.section-heading p');
  if(description)description.textContent=`追踪每个包裹的下一站${nextPage?` · 已读取 ${shipments.length} / ${totalShipments} 票，搜索与统计基于已加载运单`:''}`;
  const hint=app.querySelector('.filter-hint');
  if(hint)hint.innerHTML=`${icon('clock',13)} 最近更新 ${escape(shipments.map(s=>s.updatedAt).sort().at(-1)?.slice(5) || '暂无')}`;
  updateWorkspace();
}

function filtered() {
  let list = filterShipments(shipments,{query,status:filter==='moving'?'all':filter});
  if (filter==='moving') list = list.filter(s=>['shipped','transit','customs','delivery'].includes(s.status));
  return list;
}

function workspace() {
  const list = filtered();
  if (!list.some(s=>s.id===selectedId)) selectedId = list[0]?.id;
  const selected = list.find(s=>s.id===selectedId);
  if (!list.length) return `<div class="empty-state">${icon(shipments.length?'search':'box',38)}<h3>${refreshing?'正在读取运单…':shipments.length?'没有找到相关运单':'暂无运单'}</h3><p>${shipments.length?'试试其他运单号、物品名称或目的地':connectionError?'暂时无法读取，请重试。':'包裹预报经运营确认并建立运单后，会显示在这里。'}</p>${shipments.length?'<button class="button secondary" data-action="reset-filter">查看全部运单</button>':''}${nextPage?'<button class="button secondary" data-action="load-more">加载更多运单</button>':''}</div>`;
  return `<div class="shipment-list" aria-label="运单列表">${list.map(shipmentCard).join('')}<div class="list-end ${nextPage?'has-more':''}">${nextPage?`已加载 ${shipments.length} / ${totalShipments} 票 <button class="text-button" data-action="load-more" ${refreshing?'disabled':''}>加载更多</button>`:`已展示 ${list.length} 票运单`}</div></div><div class="shipment-detail">${detail(selected)}</div>`;
}

function shipmentCard(s) {
  return `<button class="shipment-card ${s.id===selectedId?'selected':''}" data-action="select-shipment" data-id="${escape(s.id)}" aria-pressed="${s.id===selectedId}"><div class="shipment-card-top"><span class="shipment-id">${escape(s.id)}</span>${badge(s)}</div><div class="shipment-route"><strong>${escape(s.origin.city)}</strong><span class="route-line"><i></i>${icon('arrow',17)}</span><strong>${escape(s.destination.city)}</strong><span class="method-badge">${s.method.includes('空')?icon('plane',13):icon('ship',13)}${s.method.includes('空')?'空运':'海运'}</span></div><div class="shipment-goods">${icon('box',15)}<span>${escape(s.goods)}</span><small>${s.pieces} 件 · ${escape(weightLabel(s))}</small></div><div class="shipment-card-bottom"><span>${icon('pin',13)}${escape(s.location)}</span><span>${s.status==='delivered'?'已送达':s.eta?'预计 '+escape(s.eta.slice(5).replace('-','月'))+'日':'送达时间待确认'}</span></div></button>`;
}

function detail(s) {
  if (!s) return '';
  const st = statusOf(s);
  const timeline = expandedTimeline?s.timeline:s.timeline.slice(0,3);
  return `<div class="detail-heading"><div class="detail-route"><span class="detail-icon">${icon(s.method.includes('空')?'plane':'ship',21)}</span><div><h3>${escape(s.origin.city)}<span>${icon('arrow',17)}</span>${escape(s.destination.city)}</h3><div>${escape(s.method)}<span>·</span>${escape(s.id)} <button class="icon-button copy-button" data-action="copy-id" data-id="${escape(s.id)}" aria-label="复制运单号">${icon('copy',12)}</button></div></div></div><div class="detail-heading-actions">${session.role==='admin'?`<button class="button secondary small-button" data-action="edit-shipment" data-id="${escape(s.id)}">${icon('edit',14)} 更新轨迹</button>`:`<span class="route-live"><i></i> 运输路线</span>`}</div></div>
    ${renderRouteMap(s)}<p class="map-disclaimer">运输路线为示意，当前位置以物流轨迹节点为准，非实时 GPS。</p>
    <div class="journey-summary"><div><span>${icon('pin',14)} 当前位置</span><strong>${escape(s.location)}</strong></div><div><span>${icon('calendar',14)} ${s.status==='delivered'?'送达日期':'预计送达'}</span><strong>${deliveryDate(s)?escape(deliveryDate(s).slice(5).replace('-','月'))+'日':'待确认'}<small>${s.status==='delivered'?'已签收':'参考时效'}</small></strong></div><div><span>${icon('box',14)} 包裹信息</span><strong>${s.pieces} 件 <small>/</small> ${escape(weightLabel(s))}</strong></div></div>
    <div class="journey-steps" aria-label="运输进度">${STATUS_OPTIONS.map((step,i)=>`<div class="journey-step ${i<=st.step?'complete':''} ${i===st.step?'current':''}"><span class="step-node">${i<st.step?icon('check',10):i===st.step?'<i></i>':''}</span><span>${escape(step.label)}</span></div>`).join('')}</div>
    <div class="timeline-section"><div class="timeline-heading"><h4>物流轨迹</h4><button class="text-button" data-action="shipment-info" data-id="${escape(s.id)}">运单详情 ${icon('chevron',13)}</button></div><ol class="timeline">${!timeline.length?'<li class="timeline-empty">暂无轨迹，等待运营更新。</li>':''}${timeline.map((event,i)=>`<li class="${i===0?'latest':''}"><span class="timeline-node">${i===0?'<i></i>':''}</span><div><strong>${escape(event.title)}</strong><p>${escape(event.description)}</p><span class="timeline-location">${icon('pin',11)} ${escape(event.location)}</span></div><time>${escape(event.time.slice(5,10))}<span>${escape(event.time.slice(11,16))}</span></time></li>`).join('')}</ol>${s.timeline.length>3?`<button class="expand-timeline" data-action="expand-timeline">${expandedTimeline?'收起轨迹':'查看全部 '+s.timeline.length+' 条轨迹'} ${icon('down',13)}</button>`:''}</div>`;
}

function updateWorkspace() {
  const target = document.querySelector('#tracking-workspace');
  if (target) { target.innerHTML = workspace(); zoom=1; }
}

function addressesPage() {
  const customerCode = session.customerCode || '待分配';
  return `<section class="page-heading"><div><div class="eyebrow">YOUR NEXT STOP</div><h1>仓库地址<span class="heading-dot">.</span></h1><p>购物寄到集运仓，我们替您开启下一程。</p></div></section><div class="info-banner">${icon('help',19)}<span>您的会员编号：<strong>${escape(customerCode)}</strong>。寄件前请向运营确认仓库地址、收件人和收货安排。</span></div><section class="warehouse-pending"><span class="address-icon">${icon('warehouse',29)}</span><h2>仓库收货资料待配置</h2><p>请联系客服取得当前有效的仓库收货资料，并在收件信息中注明会员编号。</p><div class="contact-details">${contactLinks()}</div><button class="button secondary" data-action="support">${icon('support',17)} 联系客服</button></section>`;
}

function helpPage() {
  const faqs = [
    ['这里显示的运输位置是实时 GPS 吗？','地图展示物流节点之间的路线示意，非实时 GPS。当前位置以最新物流轨迹的扫描或运营记录为准。'],
    ['如何查询自己的包裹？','使用公司分配的客户账号登录。每个客户仅能读取属于自己的运单，可通过运单号、物品、目的地搜索已加载的记录。'],
    ['管理员如何管理数据？','管理员登录后可在运单详情更新轨迹，也可通过“后台管理”维护客户、运单、轨迹和包裹预报。权限由服务器验证。'],
    ['提交包裹预报后就已入库吗？','预报只代表您已提交包裹资料，需等待运营确认。仓库实际收货并建立运单后，才能在运单列表查看运输状态。'],
    ['不同设备可以看到同样的运单吗？',demoMode?'当前为静态展示，仅使用本页内存中的示例数据，刷新后恢复。':'可以。同一账号在不同设备登录后读取服务器中的相同运单。页面可见时每 30 秒自动刷新，也可手动刷新。'],
    ['主域名暂时打不开怎么办？','请使用提前收藏的备用地址。页面完全无法加载时无法显示备用入口；切换地址后需要重新登录。']
  ];
  return `<section class="page-heading"><div><div class="eyebrow">ALWAYS HERE FOR YOU</div><h1>集运，其实很简单<span class="heading-dot">.</span></h1><p>关于包裹的每一个问题，我们都认真解答。</p></div><button class="button primary" data-action="support">${icon('support',18)} 联系客服</button></section><section class="how-it-works">${[['01','warehouse','寄到集运仓','先确认有效的仓库地址及会员编号。'],['02','box','提交包裹预报','填写包裹资料，等待运营确认。'],['03','ship','安排国际运输','实际收货建立运单后，追踪运输节点。'],['04','check','送达您的家门','随时查看轨迹，安心等待签收。']].map(([n,ico,title,text])=>`<article><span class="how-number">${n}</span><div class="how-icon">${icon(ico,26)}</div><h3>${title}</h3><p>${text}</p></article>`).join('')}</section><section class="help-contact-card"><h2>联系我们</h2><div class="contact-details">${contactLinks()}</div>${accessLinks()}</section><section class="faq-card"><h2>常见问题</h2>${faqs.map(([q,a],i)=>`<details ${disclosureAttributes(`faq-${i}`,i===0)}><summary>${q}${icon('plus',17)}</summary><p>${a}</p></details>`).join('')}${demoMode?'<div class="faq-footer"><span>重新开始体验初始案例</span><button class="text-button" data-action="reset-demo">重置演示数据</button></div>':''}</section>`;
}

function openModal(title, body, size = '') {
  lastModalFocus = document.activeElement;
  modalRoot.innerHTML = `<div class="modal-overlay"><section class="modal ${size}" role="dialog" aria-modal="true" aria-labelledby="modal-title"><header class="modal-header"><h2 id="modal-title">${escape(title)}</h2><button class="icon-button" data-action="close-modal" aria-label="关闭弹窗">${icon('close',21)}</button></header>${body}</section></div>`;
  document.body.classList.add('modal-open');
  requestAnimationFrame(()=>modalRoot.querySelector('input, select, button')?.focus());
}
function closeModal() { modalRoot.innerHTML=''; document.body.classList.remove('modal-open'); lastModalFocus?.focus(); }

function newShipmentModal() {
  openModal('新增包裹预报', `<form id="new-shipment-form" class="modal-form" data-submission-key="${eventKey()}"><p class="modal-intro">提前告诉我们包裹信息，抵达仓库后更快入库。</p><label for="tracking-number">国内快递单号 <em>*</em></label><input id="tracking-number" name="trackingNumber" placeholder="如 SF1234567890123" maxlength="40" pattern="[A-Za-z0-9\\x2d]{6,40}" title="请输入 6–40 位字母、数字或横线" required><label for="goods">物品名称 <em>*</em></label><input id="goods" name="goods" placeholder="如 衣物、生活用品" maxlength="60" required><div class="form-columns"><div><label for="pieces">包裹件数</label><input id="pieces" name="pieces" type="number" min="1" max="99" value="1" required></div><div><label for="weight">预估重量（kg）</label><input id="weight" name="weight" type="number" min="0.1" max="1000" step="0.1" value="1" required></div></div><div class="form-columns"><div><label for="destination">目的地</label><select id="destination" name="destination"><option value="KUL">马来西亚 · 吉隆坡</option><option value="SIN">新加坡</option><option value="BKK">泰国 · 曼谷</option></select></div><div><label for="method">运输方式</label><select id="method" name="method"><option>海运专线</option><option>空运专线</option></select></div></div><p class="form-note">${icon('help',15)} 提交预报后需等待运营确认，不代表包裹已入库。</p><p class="form-error" id="new-shipment-error" role="alert"></p><div class="modal-actions"><button class="button secondary" type="button" data-action="close-modal">取消</button><button class="button primary" type="submit">提交预报 ${icon('arrow',16)}</button></div></form>`);
}

function editShipmentModal(id) {
  const s = shipments.find(s=>s.id===id); if (!s || session?.role!=='admin') return;
  openModal('更新运输轨迹', `<form id="edit-shipment-form" class="modal-form" data-id="${escape(id)}" data-source-key="${eventKey()}"><div class="editing-shipment"><span>${icon('box',20)} ${escape(id)}</span><strong>${escape(s.origin.city)} → ${escape(s.destination.city)}</strong></div><label for="edit-status">运输状态</label><select id="edit-status" name="status">${STATUS_OPTIONS.map(o=>`<option value="${o.id}" ${s.status===o.id?'selected':''}>${o.label}</option>`).join('')}</select><label for="edit-location">当前位置 <em>*</em></label><input id="edit-location" name="location" value="${escape(s.location)}" maxlength="80" placeholder="如 吉隆坡清关中心" required><label for="edit-note">轨迹说明 <em>*</em></label><textarea id="edit-note" name="note" maxlength="250" rows="3" placeholder="如 包裹已抵达吉隆坡，正在安排清关" required></textarea><p class="form-note">保存后将新增一条物流轨迹，客户视图同步显示。</p><p class="form-error" id="edit-error" role="alert"></p><div class="modal-actions"><button type="button" class="button secondary" data-action="close-modal">取消</button><button class="button primary" type="submit">${icon('check',17)} 保存更新</button></div></form>`);
}

function shipmentInfo(id) {
  const s=shipments.find(s=>s.id===id); if (!s) return;
  openModal('运单详情', `<div class="shipment-info"><div class="info-id"><span>${escape(s.id)}</span>${badge(s)}</div><div class="info-route"><strong>${escape(s.origin.city)}</strong>${icon('arrow',24)}<strong>${escape(s.destination.city)}</strong></div><dl>${[['物品名称',s.goods],['运输方式',s.method],['包裹规格',`${s.pieces} 件 · ${weightLabel(s)} · ${volumeLabel(s)}`],['创建日期',s.createdAt],['收件人',s.recipient.name],['联系电话',s.recipient.phone],['收货地址',s.recipient.address],...(s.trackingNumber?[['国内快递单号',s.trackingNumber]]:[])].map(([label,v])=>`<div><dt>${label}</dt><dd>${escape(v)}</dd></div>`).join('')}</dl><div class="modal-actions"><button class="button secondary" data-action="copy-id" data-id="${escape(s.id)}">${icon('copy',16)} 复制单号</button><button class="button primary" data-action="close-modal">完成</button></div></div>`);
}

async function copyText(value) {
  try { await navigator.clipboard.writeText(value); toast('已复制到剪贴板'); }
  catch { openModal('复制信息',`<div class="modal-form"><p class="modal-intro">请选中以下内容进行复制：</p><textarea rows="4" readonly>${escape(value)}</textarea><div class="modal-actions"><button class="button primary" data-action="close-modal">完成</button></div></div>`); modalRoot.querySelector('textarea')?.select(); }
}

document.addEventListener('click', async e => {
  const button = e.target.closest('[data-action]');
  if (!button || button.disabled) { if (e.target.classList.contains('modal-overlay')) closeModal(); return; }
  const action=button.dataset.action;
  if (action==='login-role') { loginRole=button.dataset.role; loginError=''; renderLogin(); }
  if (action==='toggle-password') { const input=document.querySelector('#password'); input.type=input.type==='password'?'text':'password'; }
  if (action==='demo-login' && demoMode) { const account=DEMO_ACCOUNTS[loginRole]; acceptUser({...authenticate(loginRole,account.username,account.password),customerCode:'DEMO-001'}); toast('已进入静态展示，数据仅供体验'); }
  if (action==='login-help') openModal('登录帮助',`<div class="modal-form"><p class="modal-intro">${demoMode?'使用页面下方演示账号或一键体验。':'请使用公司分配的账号和密码。忘记密码或尚未开通账号，请联系公司客服。'}</p><div class="contact-details">${contactLinks()}</div>${accessLinks()}</div>`);
  if (action==='logout') {
    button.disabled=true;
    try { if (!demoMode) await api.logout(); clearSession(); toast('已安全退出'); }
    catch(error) { if(error.status===401) clearSession(); else {button.disabled=false;toast(`退出失败：${error.message}`);} }
  }
  if (action==='retry-connection' && !demoMode) {if(session) {await loadConfig();await refreshShipments();render();}else {initializing=true;await initialize();}}
  if (action==='refresh-shipments') await refreshShipments();
  if (action==='load-more' && nextPage) await refreshShipments({append:true});
  if (action==='nav') { page=button.dataset.page; if (page==='shipments') {filter='all';query='';} render(); window.scrollTo({top:0,behavior:'smooth'}); }
  if (action==='filter') { filter=button.dataset.filter; expandedTimeline=false; render(); }
  if (action==='select-shipment') { selectedId=button.dataset.id; expandedTimeline=false; zoom=1; updateWorkspace(); }
  if (action==='clear-search') { query=''; render(); document.querySelector('#shipment-search')?.focus(); }
  if (action==='reset-filter') { query='';filter='all';render(); }
  if (action==='new-shipment' && session?.role==='customer') newShipmentModal();
  if (action==='close-modal') closeModal();
  if (action==='copy-id') copyText(button.dataset.id);
  if (action==='copy-access') copyText(button.dataset.url);
  if (action==='expand-timeline') { expandedTimeline=!expandedTimeline; updateWorkspace(); }
  if (action==='shipment-info') shipmentInfo(button.dataset.id);
  if (action==='edit-shipment') editShipmentModal(button.dataset.id);
  if (action==='support') openModal('专属客服，一路相伴',`<div class="support-modal"><span class="large-support-icon">${icon('support',34)}</span><h3>很高兴为您服务</h3><p>如需查询包裹，请提供您的运单号。</p><div class="support-contact contact-details">${contactLinks()}</div>${accessLinks()}</div>`);
  if (action==='notifications') openModal('物流通知',`<div class="notification-list">${shipments.length?shipments.slice(0,3).map(s=>`<button data-action="notification-shipment" data-id="${escape(s.id)}"><span class="notification-icon">${icon('box',20)}</span><div><strong>${escape(s.id)} · ${escape(statusOf(s).label)}</strong><p>${escape(s.timeline[0]?.description || s.location)}</p><span>${escape(s.updatedAt)}</span></div>${icon('chevron',16)}</button>`).join(''):'<p class="modal-intro">暂无物流通知</p>'}</div>`);
  if (action==='notification-shipment') { selectedId=button.dataset.id; page='overview';filter='all';query='';closeModal();render(); }
  if (action==='map-zoom-in'||action==='map-zoom-out') { zoom=Math.max(1,Math.min(1.7,zoom+(action==='map-zoom-in' ? 0.2 : -0.2))); const svg=document.querySelector('.map-illustration'); if(svg) {svg.style.transform=`scale(${zoom})`;svg.style.transformOrigin='center';svg.style.transition='transform .25s';} }
  if (action==='reset-demo' && demoMode) openModal('重置演示数据',`<div class="modal-form"><p class="modal-intro">将恢复 6 票初始示例运单，清除本页的轨迹演示更新。</p><div class="modal-actions"><button class="button secondary" data-action="close-modal">取消</button><button class="button primary" data-action="confirm-reset">确认重置</button></div></div>`);
  if (action==='confirm-reset' && demoMode) {shipments=getShipments(null); totalShipments=shipments.length;selectedId=shipments[0]?.id;closeModal();render();toast('演示数据已恢复');}
});

document.addEventListener('input', e=>{if(e.target.id==='shipment-search'){ query=e.target.value; expandedTimeline=false;updateWorkspace(); }});

document.addEventListener('submit', async e=>{
  const form=e.target;
  if (!['login-form','edit-shipment-form','new-shipment-form'].includes(form.id)) return;
  e.preventDefault();
  const fd=new FormData(form), submit=form.querySelector('[type="submit"]');
  if(submit.disabled)return;
  submit.disabled=true;
  if (form.id==='login-form') {
    try {
      const credentials={username:String(fd.get('username')).trim(),password:String(fd.get('password')),remember:fd.get('remember')==='on',role:loginRole};
      const result=demoMode?{user:authenticate(loginRole,credentials.username,credentials.password)}:await api.login(credentials);
      if(!result.user)throw new Error('演示账号或密码不正确。');
      acceptUser({...result.user,...(demoMode?{customerCode:'DEMO-001'}:{})});
      if(!demoMode)await refreshShipments();
      if(session)toast(`欢迎回来，${session.name || credentials.username}`);
    } catch(error) { loginError=error.message;const errorElement=document.querySelector('#login-error');if(errorElement)errorElement.textContent=loginError; }
    finally {submit.disabled=false;}
  }
  if (form.id==='edit-shipment-form') {
    if(session?.role!=='admin')return;
    try {
      const event={status:fd.get('status'),location:String(fd.get('location')).trim(),note:String(fd.get('note')).trim(),sourceKey:form.dataset.sourceKey};
      if(demoMode)shipments=updateShipment(shipments,form.dataset.id,event);
      else await api.addEvent(form.dataset.id,event);
      closeModal();
      if(shipmentRequest?.version===sessionVersion)await shipmentRequest.promise;
      const synced=demoMode?true:await refreshShipments();render();
      toast(demoMode?'静态轨迹演示已更新，仅本页有效':synced?'运输轨迹已保存到服务器':'轨迹已保存，列表刷新失败，请手动刷新');
    } catch(error) { if(error.status===401)clearSession('登录已过期，请重新登录。');else form.querySelector('#edit-error').textContent=error.message; }
    finally {submit.disabled=false;}
  }
  if (form.id==='new-shipment-form') {
    if(session?.role!=='customer')return;
    const goods=String(fd.get('goods')).trim(),trackingNumber=String(fd.get('trackingNumber')).trim();
    try {
      if(!validTrackingNumber(trackingNumber))throw new Error('请输入 6–40 位字母、数字或横线组成的快递单号');
      if(!goods)throw new Error('请填写物品名称');
      const prealert={submissionKey:form.dataset.submissionKey,trackingNumber,goods,pieces:Number(fd.get('pieces')),weight:Number(fd.get('weight')),method:fd.get('method'),destination:fd.get('destination')};
      if(demoMode) {closeModal();toast('静态展示：预报填写完成，真实提交后需等待运营确认');}
      else {
        const result=await api.createPrealert(prealert);
        if(!result.prealert?.number)throw new Error('服务器未返回预报确认，请联系运营核实后再重试。');
        closeModal();toast(`预报 ${result.prealert.number} 已提交，待运营确认；尚未入库`);
      }
    } catch(error) {if(error.status===401)clearSession('登录已过期，请重新登录。');else form.querySelector('#new-shipment-error').textContent=error.message;}
    finally {submit.disabled=false;}
  }
});

document.addEventListener('keydown',e=>{
  if(!modalRoot.innerHTML)return;
  if(e.key==='Escape')closeModal();
  if(e.key==='Tab'){const items=[...modalRoot.querySelectorAll('button,input,select,textarea,a[href]')].filter(el=>!el.disabled);const first=items[0],last=items.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}}
});
document.addEventListener('toggle',e=>{if(e.target.matches?.('details[data-disclosure]'))disclosureState.set(e.target.dataset.disclosure,e.target.open);},true);
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'&&session&&!modalRoot.innerHTML)refreshShipments();});
initialize();

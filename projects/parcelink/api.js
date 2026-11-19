/** Same-origin transport. Sessions and authorization are owned by Django. */
export class ApiError extends Error {
  constructor(message, status = 0, details = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }
}

export function safeApiPath(value, baseUrl = globalThis.location?.href || 'http://localhost/') {
  if (typeof value !== 'string' || !value.startsWith('/api/') || value.startsWith('//') || /[\\\r\n]/.test(value)) {
    throw new ApiError('服务器返回了无效的分页地址');
  }
  const base = new URL(baseUrl);
  const url = new URL(value, base);
  if (url.origin !== base.origin || !url.pathname.startsWith('/api/')) throw new ApiError('分页地址必须使用本站接口');
  return url.pathname + url.search;
}

function errorMessage(body, fallback) {
  if (typeof body?.error === 'string') return body.error;
  if (typeof body?.detail === 'string') return body.detail;
  if (typeof body?.message === 'string') return body.message;
  if (body && typeof body === 'object') {
    const messages = Object.values(body).flat().filter(value => typeof value === 'string');
    if (messages.length) return messages.join('；');
  }
  return fallback;
}

function validShipment(item) {
  const place = value => value && ['city','country','code'].every(key => typeof value[key] === 'string');
  return item && ['id','status','goods','method','location','eta','createdAt','updatedAt'].every(key => typeof item[key] === 'string')
    && ['warehouse','shipped','transit','customs','delivery','delivered'].includes(item.status)
    && ['pieces','progress'].every(key => Number.isFinite(item[key]) && item[key] >= 0)
    && ['weight','volume'].every(key => item[key] === null || (Number.isFinite(item[key]) && item[key] >= 0))
    && place(item.origin) && place(item.destination)
    && item.recipient && ['name','phone','address'].every(key => typeof item.recipient[key] === 'string')
    && Array.isArray(item.timeline) && item.timeline.every(event => event && ['title','description','location','time','status'].every(key => typeof event[key] === 'string'));
}

export function createApi({ fetchImpl = globalThis.fetch?.bind(globalThis), baseUrl = globalThis.location?.href || 'http://localhost/' } = {}) {
  let csrfToken = null;
  async function request(path, { method = 'GET', body } = {}) {
    const safePath = safeApiPath(path, baseUrl);
    const headers = { Accept: 'application/json' };
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (method !== 'GET') {
      if (!csrfToken) await refreshCsrf();
      headers['X-CSRFToken'] = csrfToken;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(),15000);
    try {
      let response;
      try {
        response = await fetchImpl(safePath, { method, credentials: 'same-origin', redirect: 'error', signal:controller.signal, headers, cache: 'no-store', ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
      } catch {
        throw new ApiError(controller.signal.aborted ? '连接服务器超时，请稍后重试。' : '无法连接服务器，请检查网络后重试。');
      }
      if (response.status === 204 && response.ok) return null;
      let data;
      try { data = await response.json(); }
      catch { throw new ApiError(response.ok ? '服务器返回了无法读取的数据。' : '服务暂时不可用，请稍后重试。', response.status); }
      if (!response.ok) throw new ApiError(errorMessage(data, `请求失败（${response.status}），请重试。`), response.status, data);
      return data;
    } finally { clearTimeout(timer); }
  }
  async function refreshCsrf() {
    const data = await request('/api/auth/csrf/');
    if (typeof data?.csrfToken !== 'string' || !data.csrfToken) throw new ApiError('无法获取安全校验令牌，请刷新页面。');
    csrfToken = data.csrfToken;
    return csrfToken;
  }
  return {
    publicConfig: () => request('/api/public/config/'),
    me: () => request('/api/auth/me/'),
    async login(credentials) {
      const result = await request('/api/auth/login/', { method: 'POST', body: credentials });
      // Django rotates the token during login. Never reuse the anonymous token.
      csrfToken = null;
      await refreshCsrf();
      return result;
    },
    async logout() {
      const result = await request('/api/auth/logout/', { method: 'POST', body: {} });
      csrfToken = null;
      return result;
    },
    async shipments(next = '/api/shipments/?limit=100') {
      const data = await request(next);
      if (!Array.isArray(data?.results) || !data.results.every(validShipment) || !Number.isInteger(data.count) || data.count < 0) throw new ApiError('服务器返回了无效的运单列表。');
      if (data.next !== null && data.next !== undefined) data.next = safeApiPath(data.next, baseUrl);
      return data;
    },
    addEvent: (number, event) => request(`/api/shipments/${encodeURIComponent(number)}/events/`, { method: 'POST', body: event }),
    createPrealert: prealert => request('/api/package-prealerts/', { method: 'POST', body: prealert }),
  };
}

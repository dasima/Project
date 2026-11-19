/** Optional static fallback. Supply real values here or through Django public config. */
export const SITE_CONFIG = {
  company: { name: '项目名称待定', phone: '000-00000000', email: 'support@example.com', isPlaceholder: true },
  access: { primaryDomain: null, backupDomains: [] },
};

export function safePublicUrl(value) {
  if (typeof value !== 'string' || !value.trim() || /[\\\s]/.test(value.trim())) return null;
  const text = value.trim();
  if (text.startsWith('/')) return null;
  // Bare hostnames are published as HTTPS links. Other schemes are never accepted.
  const candidate = /^[A-Za-z][A-Za-z\d+.-]*:/.test(text) ? text : `https://${text}`;
  try {
    const url = new URL(candidate);
    const local = url.hostname === 'localhost' || url.hostname === '127.0.0.1' || url.hostname === '[::1]';
    if (url.protocol !== 'https:' && !(local && url.protocol === 'http:')) return null;
    if (!url.hostname || url.username || url.password || url.search || url.hash || url.pathname !== '/') return null;
    return url.origin;
  } catch { return null; }
}

export function normalizeSiteConfig(value = {}) {
  const company = value.company || {};
  const access = value.access || {};
  const text = item => typeof item === 'string' && item.trim() ? item.trim() : null;
  const phone = text(company.phone);
  const email = text(company.email);
  const primaryDomain = safePublicUrl(access.primaryDomain);
  return {
    company: {
      name: text(company.name) || SITE_CONFIG.company.name,
      isPlaceholder: company.isPlaceholder === true,
      phone: phone && /^[+\d][\d\s().-]{4,40}$/.test(phone) ? phone : null,
      email: email && /^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$/.test(email) ? email : null,
    },
    access: {
      primaryDomain,
      backupDomains: [...new Set((Array.isArray(access.backupDomains) ? access.backupDomains : []).map(safePublicUrl).filter(url => url && url !== primaryDomain))],
    },
  };
}

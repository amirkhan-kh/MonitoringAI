import { navigateTo } from "../navigation";
import { translateUiText } from "../i18n";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || (import.meta.env.PROD ? "/api" : "http://localhost:8000");
const TOKEN_KEY = "monitoring_admin_session";
const SELECTED_BRAND_KEY = "monitoring_selected_brand_id";
const GET_CACHE = new Map();
const GET_INFLIGHT = new Map();
let CACHE_VERSION = 0;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function getUiLanguage() {
  const language = window.localStorage.getItem("monitoring_ui_language") || "uz";
  return ["uz", "ru", "en"].includes(language) ? language : "uz";
}

export function getSession() {
  try {
    return JSON.parse(window.localStorage.getItem(TOKEN_KEY) || "null");
  } catch {
    return null;
  }
}

export function getToken() {
  return getSession()?.access_token || null;
}

export function isAuthed() {
  return !!getToken();
}

export function clearSession() {
  window.localStorage.removeItem(TOKEN_KEY);
}

export function readSelectedBrandId() {
  const value = window.localStorage.getItem(SELECTED_BRAND_KEY) || "";
  return validUuid(value) ? value : "";
}

export function saveSelectedBrandId(brandId) {
  if (validUuid(brandId)) {
    window.localStorage.setItem(SELECTED_BRAND_KEY, brandId);
    return brandId;
  }
  window.localStorage.removeItem(SELECTED_BRAND_KEY);
  return "";
}

export function resolveSelectedBrandId(brands, preferredBrandId = readSelectedBrandId()) {
  const rows = Array.isArray(brands) ? brands : [];
  const selected = rows.find((brand) => brand.id === preferredBrandId && brand.active !== false)
    || rows.find((brand) => brand.active !== false)
    || rows[0];
  return saveSelectedBrandId(selected?.id || "");
}

function pathFromCacheKey(key) {
  const index = key.indexOf(":/");
  return index >= 0 ? key.slice(index + 1) : key;
}

export function clearApiCache(prefixes = null) {
  CACHE_VERSION += 1;
  if (!prefixes) {
    GET_CACHE.clear();
    GET_INFLIGHT.clear();
    return;
  }
  const prefixList = Array.isArray(prefixes) ? prefixes : [prefixes];
  for (const key of GET_CACHE.keys()) {
    const path = pathFromCacheKey(key);
    if (prefixList.some((prefix) => path.startsWith(prefix))) GET_CACHE.delete(key);
  }
  for (const key of GET_INFLIGHT.keys()) {
    const path = pathFromCacheKey(key);
    if (prefixList.some((prefix) => path.startsWith(prefix))) GET_INFLIGHT.delete(key);
  }
}

export async function login(username, password) {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) {
    throw new Error(await friendlyError(response));
  }
  const session = await response.json();
  window.localStorage.setItem(TOKEN_KEY, JSON.stringify(session));
  return session;
}

export function logout() {
  clearSession();
  clearApiCache();
  navigateTo("/login", { replace: true });
}

// Back-compat helpers used by Profile.jsx. saveAdminSession MERGES into the stored
// session so profile edits never clobber the auth access_token.
export const readAdminSession = getSession;
export const clearAdminSession = clearSession;
export function saveAdminSession(patch) {
  const next = { ...(getSession() || {}), ...(patch || {}) };
  window.localStorage.setItem(TOKEN_KEY, JSON.stringify(next));
  return next;
}

export async function api(path, options = {}) {
  const token = getToken();
  const method = (options.method || "GET").toUpperCase();
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        "Content-Type": "application/json",
        "Accept-Language": getUiLanguage(),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers || {}),
      },
      ...options,
    });
  } catch {
    throw new Error(translateUiText(`Serverga ulanib bo'lmadi (${API_BASE_URL}). Backend ishga tushganini tekshiring.`));
  }

  if (response.status === 401) {
    clearSession();
    clearApiCache();
    if (!window.location.pathname.startsWith("/login")) {
      navigateTo("/login", { replace: true });
    }
    throw new Error(translateUiText("Sessiya tugadi. Qaytadan kiring."));
  }

  if (!response.ok) {
    throw new Error(await friendlyError(response));
  }

  const data = await response.json();
  if (method !== "GET") clearApiCache();
  return data;
}

export async function cachedApi(path, ttlMs = 15000) {
  const key = `${getToken() || ""}:${getUiLanguage()}:${path}`;
  const cached = GET_CACHE.get(key);
  const now = Date.now();
  if (cached && now - cached.time < ttlMs) return cached.value;
  if (GET_INFLIGHT.has(key)) return GET_INFLIGHT.get(key);
  const cacheVersion = CACHE_VERSION;
  const request = api(path)
    .then((value) => {
      if (cacheVersion === CACHE_VERSION) {
        GET_CACHE.set(key, { value, time: Date.now() });
      }
      return value;
    })
    .finally(() => GET_INFLIGHT.delete(key));
  GET_INFLIGHT.set(key, request);
  return request;
}

function withQuery(path, params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, value);
    }
  });
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}

function brandPath(path, brandId) {
  return withQuery(path, { brand_id: validUuid(brandId) ? brandId : "" });
}

function brandLimitPath(path, brandId, limit = 100) {
  return withQuery(path, { brand_id: validUuid(brandId) ? brandId : "", limit });
}

function validUuid(value) {
  return UUID_PATTERN.test(String(value || "").trim());
}

function uuidPath(prefix, value) {
  if (!validUuid(value)) throw new Error(translateUiText("Noto'g'ri identifikator. Sahifani yangilab qayta urinib ko'ring."));
  return `${prefix}/${value}`;
}

async function friendlyError(response) {
  let detail = "";
  const raw = await response.text().catch(() => "");
  if (raw) {
    try {
      const data = JSON.parse(raw);
      if (typeof data.detail === "string") {
        detail = data.detail;
      } else if (Array.isArray(data.detail)) {
        detail = data.detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
      } else {
        detail = data.message || raw;
      }
    } catch {
      detail = raw;
    }
  }
  detail = (detail || "").trim();
  if (detail.length > 300) detail = `${detail.slice(0, 300)}…`;
  const status = `${response.status} ${response.statusText}`.trim();
  return detail ? `${status} · ${translateUiText(detail)}` : status;
}

export const endpoints = {
  health: () => api("/health"),
  brands: () => cachedApi("/brands", 30000),
  brandTaxonomy: () => cachedApi("/brand-taxonomy", 300000),
  createBrand: (payload) =>
    api("/brands", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateBrand: (brandId, payload) =>
    api(uuidPath("/brands", brandId), {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  brandProfileSuggestions: (payload) =>
    api("/brands/profile-suggestions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  botStatus: () => cachedApi("/telegram/bot/status", 10000),
  backfillSessionStatus: () => api("/telegram/backfill/session-status"),
  sourceCategories: () => cachedApi("/telegram/source-categories", 60000),
  sources: () => cachedApi("/telegram/sources", 5000),
  sourceAccessCheck: (chatIdOrUsername) =>
    api("/telegram/sources/access-check", {
      method: "POST",
      body: JSON.stringify({ chat_id_or_username: chatIdOrUsername }),
    }),
  importSources: (payload) =>
    api("/telegram/sources/import", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateSource: (sourceId, payload) =>
    api(`/telegram/sources/${sourceId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteSource: (sourceId) => api(uuidPath("/telegram/sources", sourceId), { method: "DELETE" }),
  refreshSource: (sourceId) =>
    api(`/telegram/sources/${sourceId}/refresh`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  backfillSource: (sourceId, payload = { comments_per_post: 50 }) =>
    api(`/telegram/sources/${sourceId}/backfill`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  dashboardSummary: (brandId) => cachedApi(brandPath("/dashboard/summary", brandId), 5000),
  dashboardAnalytics: (brandId, days = 30, interval = "day", timezone = "") =>
    cachedApi(withQuery("/dashboard/analytics", { days, interval, timezone, brand_id: validUuid(brandId) ? brandId : "" }), 5000),
  mentions: (brandId, limit = 100) => cachedApi(brandLimitPath("/mentions", brandId, limit), 4000),
  youtubeStatus: () => cachedApi("/youtube/status", 30000),
  youtubeSourceCategories: () => cachedApi("/youtube/source-categories", 60000),
  youtubeSources: () => cachedApi("/youtube/sources", 5000),
  youtubeImportSources: (payload) =>
    api("/youtube/sources/import", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  youtubeUpdateSource: (sourceId, payload) =>
    api(`/youtube/sources/${sourceId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  youtubeDeleteSource: (sourceId) => api(uuidPath("/youtube/sources", sourceId), { method: "DELETE" }),
  youtubeSyncSource: (sourceId, payload = { max_pages: 1, comments_per_video: 100 }) =>
    api(`/youtube/sources/${sourceId}/sync`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  youtubeMentions: (brandId, limit = 100) => cachedApi(brandLimitPath("/youtube/mentions", brandId, limit), 4000),
  youtubeSummary: (brandId) => cachedApi(brandPath("/youtube/summary", brandId), 5000),
  instagramStatus: () => cachedApi("/instagram/status", 30000),
  instagramSourceCategories: () => cachedApi("/instagram/source-categories", 60000),
  instagramSources: () => cachedApi("/instagram/sources", 5000),
  instagramConnect: (payload) => api("/instagram/sources", { method: "POST", body: JSON.stringify(payload) }),
  instagramUpdateSource: (sourceId, payload) =>
    api(`/instagram/sources/${sourceId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  instagramValidateSource: (sourceId) =>
    api(`/instagram/sources/${sourceId}/validate`, { method: "POST", body: JSON.stringify({}) }),
  instagramSyncSource: (sourceId) =>
    api(`/instagram/sources/${sourceId}/sync`, { method: "POST", body: JSON.stringify({}) }),
  instagramDeleteSource: (sourceId) => api(`/instagram/sources/${sourceId}`, { method: "DELETE" }),
  instagramMentions: (brandId, limit = 500) => cachedApi(brandLimitPath("/instagram/mentions", brandId, limit), 4000),
  instagramSummary: (brandId) => cachedApi(brandPath("/instagram/summary", brandId), 5000),
  instagramManualIngest: (payload) =>
    api("/instagram/mentions/manual", { method: "POST", body: JSON.stringify(payload) }),
  facebookStatus: () => cachedApi("/facebook/status", 30000),
  facebookSources: () => cachedApi("/facebook/sources", 5000),
  facebookConnect: (payload) => api("/facebook/sources", { method: "POST", body: JSON.stringify(payload) }),
  facebookUpdateSource: (sourceId, payload) =>
    api(`/facebook/sources/${sourceId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  facebookValidateSource: (sourceId) =>
    api(`/facebook/sources/${sourceId}/validate`, { method: "POST", body: JSON.stringify({}) }),
  facebookDeleteSource: (sourceId) => api(`/facebook/sources/${sourceId}`, { method: "DELETE" }),
  facebookMentions: (brandId, limit = 100) => cachedApi(brandLimitPath("/facebook/mentions", brandId, limit), 4000),
  facebookSummary: (brandId) => cachedApi(brandPath("/facebook/summary", brandId), 5000),
  facebookManualIngest: (payload) =>
    api("/facebook/mentions/manual", { method: "POST", body: JSON.stringify(payload) }),
  eventsUrl: () => {
    const token = getToken();
    return `${API_BASE_URL}/events${token ? `?access_token=${encodeURIComponent(token)}` : ""}`;
  },
};

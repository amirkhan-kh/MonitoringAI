const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      ...options,
    });
  } catch {
    throw new Error(`Serverga ulanib bo'lmadi (${API_BASE_URL}). Backend ishga tushganini tekshiring.`);
  }

  if (!response.ok) {
    throw new Error(await friendlyError(response));
  }

  return response.json();
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
  return detail ? `${status} · ${detail}` : status;
}

export const endpoints = {
  health: () => api("/health"),
  brands: () => api("/brands"),
  botStatus: () => api("/telegram/bot/status"),
  backfillSessionStatus: () => api("/telegram/backfill/session-status"),
  sourceCategories: () => api("/telegram/source-categories"),
  sources: () => api("/telegram/sources"),
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
  dashboardSummary: (brandId) => api(brandId ? `/dashboard/summary?brand_id=${brandId}` : "/dashboard/summary"),
  dashboardAnalytics: (brandId, days = 30, interval = "day", timezone = "") =>
    api(`/dashboard/analytics?days=${days}&interval=${interval}${timezone ? `&timezone=${encodeURIComponent(timezone)}` : ""}${brandId ? `&brand_id=${brandId}` : ""}`),
  mentions: (brandId) => api(brandId ? `/mentions?brand_id=${brandId}` : "/mentions"),
  youtubeStatus: () => api("/youtube/status"),
  youtubeSourceCategories: () => api("/youtube/source-categories"),
  youtubeSources: () => api("/youtube/sources"),
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
  youtubeSyncSource: (sourceId, payload = { max_pages: 1, comments_per_video: 100 }) =>
    api(`/youtube/sources/${sourceId}/sync`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  youtubeMentions: (brandId) => api(brandId ? `/youtube/mentions?brand_id=${brandId}` : "/youtube/mentions"),
  youtubeSummary: (brandId) => api(brandId ? `/youtube/summary?brand_id=${brandId}` : "/youtube/summary"),
  eventsUrl: () => `${API_BASE_URL}/events`,
};

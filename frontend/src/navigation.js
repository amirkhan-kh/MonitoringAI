export const NAVIGATION_EVENT = "monitoring:navigate";

export function navigateTo(url, { replace = false } = {}) {
  const nextUrl = new URL(url, window.location.href);
  const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  const next = `${nextUrl.pathname}${nextUrl.search}${nextUrl.hash}`;
  if (next !== current) {
    if (replace) {
      window.history.replaceState(null, "", next);
    } else {
      window.history.pushState(null, "", next);
    }
  }
  window.dispatchEvent(new Event(NAVIGATION_EVENT));
}

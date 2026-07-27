/**
 * Dual-theme controller for MonitoringAI.
 * - Explicit toggle persists choice in localStorage
 * - Without a stored choice: login → light, landing + dashboard → dark
 * - init / route paint do not overwrite storage
 */

const STORAGE_KEY = "monitoring_ui_theme";
const THEMES = ["dark", "light"];

export function isLoginPath(pathname = typeof window !== "undefined" ? window.location.pathname : "") {
  if (typeof pathname !== "string") return false;
  // Auth shells (login + register) share the same visual system and light default.
  return (
    pathname === "/login"
    || pathname.startsWith("/login")
    || pathname === "/register"
    || pathname.startsWith("/register")
  );
}

/** Route-aware first-visit default (no stored preference). */
export function defaultThemeForPath(pathname) {
  return isLoginPath(pathname) ? "light" : "dark";
}

export function getStoredTheme() {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (THEMES.includes(stored)) return stored;
  } catch {
    /* ignore */
  }
  return null;
}

/**
 * Resolve active theme.
 * 1) Explicit user choice in localStorage (from toggle)
 * 2) Route default: login light, everything else dark
 */
export function resolveTheme(pathname) {
  return getStoredTheme() || defaultThemeForPath(pathname);
}

/**
 * @param {string} theme
 * @param {{ persist?: boolean }} [options]
 *   persist:true  — user intent (toggle); writes localStorage
 *   persist:false — route/init paint only; leaves storage alone
 */
export function applyTheme(theme, options = {}) {
  const { persist = false } = options;
  const next = THEMES.includes(theme) ? theme : "dark";
  document.documentElement.dataset.theme = next;
  document.documentElement.style.colorScheme = next;
  if (persist) {
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
  }
  return next;
}

/** User toggle — always persist. */
export function toggleTheme() {
  const current = document.documentElement.dataset.theme || resolveTheme();
  return applyTheme(current === "dark" ? "light" : "dark", { persist: true });
}

export function initTheme() {
  return applyTheme(resolveTheme(), { persist: false });
}

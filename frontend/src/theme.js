/**
 * Dual-theme controller for MonitoringAI.
 * - Persists choice in localStorage
 * - First visit: prefers-color-scheme
 * - Signature experience is dark-first, but light is fully supported
 */

const STORAGE_KEY = "monitoring_ui_theme";
const THEMES = ["dark", "light"];

function systemTheme() {
  if (typeof window === "undefined" || !window.matchMedia) return "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
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

export function resolveTheme() {
  return getStoredTheme() || systemTheme();
}

export function applyTheme(theme) {
  const next = THEMES.includes(theme) ? theme : "dark";
  document.documentElement.dataset.theme = next;
  document.documentElement.style.colorScheme = next;
  try {
    window.localStorage.setItem(STORAGE_KEY, next);
  } catch {
    /* ignore */
  }
  return next;
}

export function toggleTheme() {
  const current = document.documentElement.dataset.theme || resolveTheme();
  return applyTheme(current === "dark" ? "light" : "dark");
}

export function initTheme() {
  return applyTheme(resolveTheme());
}

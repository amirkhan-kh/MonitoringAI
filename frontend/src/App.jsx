import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { isAuthed } from "./api/client";
import { useDomLocalization } from "./i18n";
import { navigateTo, NAVIGATION_EVENT } from "./navigation";
import { Dashboard } from "./pages/Dashboard";
import { FacebookMonitoring } from "./pages/FacebookMonitoring";
import { InstagramMonitoring } from "./pages/InstagramMonitoring";
import { Landing } from "./pages/Landing";
import { DataDeletion, PrivacyPolicy, TermsOfService } from "./pages/Legal";
import { Login } from "./pages/Login";
import { Profile } from "./pages/Profile";
import { Register } from "./pages/Register";
import { SuperAdmin } from "./pages/SuperAdmin";
import { TelegramMonitoring } from "./pages/TelegramMonitoring";
import { YoutubeMonitoring } from "./pages/YoutubeMonitoring";
import { applyTheme, resolveTheme } from "./theme";

/** Progressive shell art: LQIP first, full webp after decode (no blank wait). */
function useShellBackground(path) {
  useEffect(() => {
    let cancelled = false;
    let raf = 0;

    function upgradeShells() {
      const shells = document.querySelectorAll(".appShell:not(.isBgReady)");
      if (!shells.length) return;
      const img = new Image();
      img.decoding = "async";
      const done = () => {
        if (cancelled) return;
        shells.forEach((el) => el.classList.add("isBgReady"));
      };
      img.onload = () => {
        if (typeof img.decode === "function") {
          img.decode().then(done).catch(done);
        } else {
          done();
        }
      };
      img.onerror = done;
      img.src = "/images/dashboard-bg.webp";
    }

    raf = window.requestAnimationFrame(upgradeShells);
    return () => {
      cancelled = true;
      window.cancelAnimationFrame(raf);
    };
  }, [path]);
}

export default function App() {
  const [path, setPath] = useState(window.location.pathname);
  const { i18n } = useTranslation();
  const language = i18n.resolvedLanguage || i18n.language || "uz";
  useDomLocalization(language);
  useShellBackground(path);

  // Route defaults (login light / product dark) when user has not toggled yet.
  useEffect(() => {
    applyTheme(resolveTheme(path), { persist: false });
  }, [path]);

  useEffect(() => {
    function updatePath() {
      setPath(window.location.pathname);
    }

    function handleDocumentClick(event) {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const anchor = event.target.closest?.("a[href]");
      if (!anchor || anchor.target || anchor.hasAttribute("download")) return;
      const href = anchor.getAttribute("href");
      if (!href || href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:")) return;
      const url = new URL(href, window.location.href);
      if (url.origin !== window.location.origin) return;
      event.preventDefault();
      navigateTo(url);
    }

    window.addEventListener("popstate", updatePath);
    window.addEventListener(NAVIGATION_EVENT, updatePath);
    document.addEventListener("click", handleDocumentClick);
    return () => {
      window.removeEventListener("popstate", updatePath);
      window.removeEventListener(NAVIGATION_EVENT, updatePath);
      document.removeEventListener("click", handleDocumentClick);
    };
  }, []);

  // Official marketing site always lives at /. Dashboard is /umumiy-dashboard.
  if (path === "/" || path === "") return <Landing key={`${language}:landing`} />;
  if (path.startsWith("/login")) return <Login key={`${language}:login`} />;
  if (path.startsWith("/register")) return <Register key={`${language}:register`} />;
  // Legal pages must stay reachable logged out — Meta's reviewer opens them that way.
  if (path.startsWith("/privacy")) return <PrivacyPolicy key={`${language}:privacy`} />;
  if (path.startsWith("/terms")) return <TermsOfService key={`${language}:terms`} />;
  if (path.startsWith("/data-deletion")) return <DataDeletion key={`${language}:data-deletion`} />;
  // Everything else is behind auth — no token means back to the login screen.
  if (!isAuthed()) {
    if (!window.location.pathname.startsWith("/login") && !window.location.pathname.startsWith("/register")) {
      window.history.replaceState(null, "", "/login");
    }
    return <Login key={`${language}:login`} />;
  }
  if (path.startsWith("/super-admin")) return <SuperAdmin key={`${language}:super-admin`} />;
  if (path.startsWith("/umumiy-dashboard")) return <Dashboard key={`${language}:dashboard`} />;
  if (path.startsWith("/profile")) return <Profile key={`${language}:profile`} />;
  if (path.startsWith("/telegram-monitoring")) return <TelegramMonitoring key={`${language}:telegram`} />;
  if (path.startsWith("/youtube-monitoring")) return <YoutubeMonitoring key={`${language}:youtube`} />;
  if (path.startsWith("/instagram-monitoring")) return <InstagramMonitoring key={`${language}:instagram`} />;
  if (path.startsWith("/facebook-monitoring")) return <FacebookMonitoring key={`${language}:facebook`} />;
  return <Dashboard key={`${language}:dashboard`} />;
}

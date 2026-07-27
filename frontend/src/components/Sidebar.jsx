import { useEffect, useState } from "react";
import { Facebook, Instagram, Languages, LayoutDashboard, LogOut, Menu, MoonStar, Shield, Sun, UserCog, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { clearApiCache, isSuperAdmin, logout } from "../api/client";
import { applyTheme, resolveTheme, toggleTheme } from "../theme";
import { TelegramIcon, YouTubeIcon } from "./BrandIcons";

const SIDEBAR_STATE_KEY = "monitoring_sidebar_collapsed";

export function Sidebar({ activePath = window.location.pathname }) {
  const { t, i18n } = useTranslation();
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem(SIDEBAR_STATE_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [theme, setTheme] = useState(() => resolveTheme());
  const language = i18n.resolvedLanguage || i18n.language || "uz";
  const navItems = [
    { href: "/umumiy-dashboard", label: t("Umumiy dashboard"), icon: LayoutDashboard },
    { href: "/telegram-monitoring", label: t("Telegram monitoring"), icon: TelegramIcon },
    { href: "/youtube-monitoring", label: t("YouTube monitoring"), icon: YouTubeIcon },
    { href: "/instagram-monitoring", label: t("Instagram monitoring"), icon: Instagram },
    { href: "/facebook-monitoring", label: t("Facebook monitoring"), icon: Facebook },
    { href: "/profile", label: t("Profil va source"), icon: UserCog },
    ...(isSuperAdmin() ? [{ href: "/super-admin", label: t("Super Admin"), icon: Shield }] : []),
  ];

  function changeLanguage(nextLanguage) {
    clearApiCache();
    window.localStorage.setItem("monitoring_ui_language", nextLanguage);
    i18n.changeLanguage(nextLanguage);
  }

  function handleThemeToggle() {
    const next = toggleTheme();
    setTheme(next);
  }

  useEffect(() => {
    document.documentElement.dataset.sidebar = collapsed ? "collapsed" : "expanded";
    try {
      window.localStorage.setItem(SIDEBAR_STATE_KEY, collapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [collapsed]);

  useEffect(() => {
    // Paint only — toggleTheme() is what persists user choice
    applyTheme(theme, { persist: false });
  }, [theme]);

  return (
    <aside className={collapsed ? "sidebar isCollapsed" : "sidebar"}>
      <div className="sidebarHeader">
        <div className="brandMark">
          <span className="brandPulse" />
          <span className="brandText">MonitoringAI</span>
        </div>
        <div className="sidebarHeaderActions">
          <button
            className="themeToggle"
            type="button"
            onClick={handleThemeToggle}
            aria-label={theme === "dark" ? t("Yorug' rejim") : t("Qorong'u rejim")}
            title={theme === "dark" ? t("Yorug' rejim") : t("Qorong'u rejim")}
          >
            <span className="themeToggleIcon" key={theme}>
              {theme === "dark" ? <Sun size={17} /> : <MoonStar size={17} />}
            </span>
          </button>
          <button
            className="sidebarToggle"
            type="button"
            onClick={() => setCollapsed((value) => !value)}
            aria-label={collapsed ? t("Sidebarni ochish") : t("Sidebarni yopish")}
            title={collapsed ? t("Sidebarni ochish") : t("Sidebarni yopish")}
          >
            <span className="sidebarToggleIcon" key={collapsed ? "open" : "close"}>
              {collapsed ? <Menu size={18} /> : <X size={18} />}
            </span>
          </button>
        </div>
      </div>

      <nav className="nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = activePath === item.href || (item.href !== "/" && activePath.startsWith(item.href));
          return (
            <a className={active ? "navItem active" : "navItem"} href={item.href} key={item.href} title={item.label}>
              <Icon size={18} />
              <span>{item.label}</span>
            </a>
          );
        })}
      </nav>

      <div className="languageSwitcher" title={t("Interfeys tili")}>
        <Languages size={17} />
        <div>
          <span className="languageLabel">{t("Til")}</span>
          <div className="languageOptions">
            {["uz", "ru", "en"].map((item) => (
              <button
                className={language === item ? "active" : ""}
                type="button"
                aria-pressed={language === item}
                key={item}
                onClick={() => changeLanguage(item)}
              >
                {item.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </div>

      <button className="navItem logoutItem" type="button" onClick={logout}>
        <LogOut size={18} />
        <span>{t("Chiqish")}</span>
      </button>
    </aside>
  );
}

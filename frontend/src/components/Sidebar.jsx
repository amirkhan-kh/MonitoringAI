import { Bot, LayoutDashboard, UserCog } from "lucide-react";
import { TelegramIcon, YouTubeIcon } from "./BrandIcons";

export function Sidebar({ botStatus, activePath = window.location.pathname }) {
  const botLabel = botStatus?.ok && botStatus.username ? `@${botStatus.username}` : "Bot ulanmagan";
  const navItems = [
    { href: "/", label: "Umumiy dashboard", icon: LayoutDashboard },
    { href: "/telegram-monitoring", label: "Telegram monitoring", icon: TelegramIcon },
    { href: "/youtube-monitoring", label: "YouTube monitoring", icon: YouTubeIcon },
    { href: "/profile", label: "Profil va source", icon: UserCog },
  ];

  return (
    <aside className="sidebar">
      <div className="brandMark">
        <span className="brandPulse" />
        <span>MonitoringAI</span>
      </div>

      <nav className="nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = activePath === item.href || (item.href !== "/" && activePath.startsWith(item.href));
          return (
            <a className={active ? "navItem active" : "navItem"} href={item.href} key={item.href}>
              <Icon size={18} />
              <span>{item.label}</span>
            </a>
          );
        })}
      </nav>

      <div className="botStatus">
        <div className="botIcon">
          <Bot size={18} />
        </div>
        <div>
          <span>Monitoring bot</span>
          <strong>{botLabel}</strong>
        </div>
        <em className={botStatus?.ok ? "state ok" : "state bad"}>{botStatus?.ok ? "online" : "offline"}</em>
      </div>
    </aside>
  );
}

import { Dashboard } from "./pages/Dashboard";
import { Login } from "./pages/Login";
import { Profile } from "./pages/Profile";
import { TelegramMonitoring } from "./pages/TelegramMonitoring";
import { YoutubeMonitoring } from "./pages/YoutubeMonitoring";

export default function App() {
  const path = window.location.pathname;
  if (path.startsWith("/login")) return <Login />;
  if (path.startsWith("/profile")) return <Profile />;
  if (path.startsWith("/telegram-monitoring")) return <TelegramMonitoring />;
  if (path.startsWith("/youtube-monitoring")) return <YoutubeMonitoring />;
  return <Dashboard />;
}

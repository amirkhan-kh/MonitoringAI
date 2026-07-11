import { useMemo, useState } from "react";
import { ArrowRight, LockKeyhole, Phone, User } from "lucide-react";

export const ADMIN_SESSION_KEY = "monitoring_admin_session";

function normalizePhone(value) {
  return value.trim().replace(/[^\d+]/g, "");
}

export function readAdminSession() {
  try {
    const raw = window.localStorage.getItem(ADMIN_SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function saveAdminSession(session) {
  window.localStorage.setItem(ADMIN_SESSION_KEY, JSON.stringify(session));
}

export function clearAdminSession() {
  window.localStorage.removeItem(ADMIN_SESSION_KEY);
}

export function Login() {
  const existing = useMemo(() => readAdminSession(), []);
  const [phone, setPhone] = useState(existing?.phone || "");
  const [login, setLogin] = useState(existing?.login || "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  function handleSubmit(event) {
    event.preventDefault();
    const nextPhone = normalizePhone(phone);
    if (!nextPhone || !login.trim() || !password.trim()) {
      setError("Telefon raqam, login va parolni to'ldiring.");
      return;
    }
    saveAdminSession({
      phone: nextPhone,
      login: login.trim(),
      display_name: login.trim(),
      signed_at: new Date().toISOString(),
    });
    window.location.href = "/profile";
  }

  return (
    <main className="loginShell">
      <section className="loginPanel">
        <div className="loginBrand">
          <span className="brandPulse" />
          <strong>MonitoringAI</strong>
        </div>
        <div className="loginIntro">
          <span>Admin access</span>
          <h1>Kirish</h1>
          <p>Brand profili, official source linklari va monitoring qamrovini boshqarish.</p>
        </div>

        <form className="loginForm" onSubmit={handleSubmit}>
          <label className="field">
            <span>Telefon raqam</span>
            <div className="inputWithIcon">
              <Phone size={17} />
              <input
                className="input"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                placeholder="+998901234567 formatida telefon raqam kiriting"
                autoComplete="tel"
              />
            </div>
          </label>
          <label className="field">
            <span>Login</span>
            <div className="inputWithIcon">
              <User size={17} />
              <input
                className="input"
                value={login}
                onChange={(event) => setLogin(event.target.value)}
                placeholder="Admin loginini kiriting"
                autoComplete="username"
              />
            </div>
          </label>
          <label className="field">
            <span>Parol</span>
            <div className="inputWithIcon">
              <LockKeyhole size={17} />
              <input
                className="input"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Admin parolini kiriting"
                autoComplete="current-password"
              />
            </div>
          </label>

          {error && <div className="errorBanner compact">{error}</div>}

          <button className="button primary fullButton" type="submit">
            <span>Profilga o'tish</span>
            <ArrowRight size={17} />
          </button>
        </form>
      </section>
    </main>
  );
}

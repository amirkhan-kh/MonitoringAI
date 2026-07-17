import { useState } from "react";
import { ArrowRight, LockKeyhole, User } from "lucide-react";
import { login as apiLogin } from "../api/client";
import { navigateTo } from "../navigation";

export function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError("Login va parolni to'ldiring.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await apiLogin(username.trim(), password);
      navigateTo("/", { replace: true });
    } catch (err) {
      setError(err.message || "Kirishda xatolik");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="loginShell">
      <section className="loginPanel">
        <div className="loginTop">
          <div className="loginBrand">
            <span className="brandPulse" />
            <strong>MonitoringAI</strong>
          </div>
        </div>
        <div className="loginIntro">
          <span>Admin access</span>
          <h1>Kirish</h1>
          <p>Brand profili, official source linklari va monitoring qamrovini boshqarish.</p>
        </div>

        <form className="loginForm" onSubmit={handleSubmit}>
          <label className="field">
            <span>Login</span>
            <div className="inputWithIcon">
              <User size={17} />
              <input
                className="input"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
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
                autoComplete="current-password"
              />
            </div>
          </label>

          {error && <div className="errorBanner compact">{error}</div>}

          <button className="button primary fullButton" type="submit" disabled={loading}>
            <span>{loading ? "Kirilmoqda..." : "Kirish"}</span>
            <ArrowRight size={17} />
          </button>
        </form>
      </section>
    </main>
  );
}

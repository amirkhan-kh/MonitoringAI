import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight, Eye, EyeOff, LockKeyhole, Radio, User } from "lucide-react";
import { login as apiLogin } from "../api/client";
import { navigateTo } from "../navigation";
import { applyTheme, getStoredTheme, resolveTheme } from "../theme";

const PLATFORMS = [
  {
    id: "telegram",
    name: "Telegram",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path
          fill="currentColor"
          d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"
        />
      </svg>
    ),
  },
  {
    id: "instagram",
    name: "Instagram",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path
          fill="currentColor"
          d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 1 0 0 12.324 6.162 6.162 0 0 0 0-12.324zM12 16a4 4 0 1 1 0-8 4 4 0 0 1 0 8zm6.406-11.845a1.44 1.44 0 1 0 0 2.881 1.44 1.44 0 0 0 0-2.881z"
        />
      </svg>
    ),
  },
  {
    id: "facebook",
    name: "Facebook",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path
          fill="currentColor"
          d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"
        />
      </svg>
    ),
  },
  {
    id: "youtube",
    name: "YouTube",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path
          fill="currentColor"
          d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"
        />
      </svg>
    ),
  },
  {
    id: "whatsapp",
    name: "WhatsApp",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path
          fill="currentColor"
          d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.435 9.884-9.85 9.884m8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 0 0-3.48-8.413z"
        />
      </svg>
    ),
  },
];

const easeOut = [0.16, 1, 0.3, 1];

function PlatformMark({ platform, size = "md" }) {
  return (
    <span className={`loginPlatformMark ${platform.id} size-${size}`} title={platform.name}>
      {platform.icon}
      <span className="srOnly">{platform.name}</span>
    </span>
  );
}

export function Login() {
  const reduceMotion = useReducedMotion();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Login defaults to light when user has never toggled; stored choice always wins.
  useEffect(() => {
    applyTheme(getStoredTheme() || resolveTheme("/login"), { persist: false });
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError("Email (yoki login) va parolni to'ldiring.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await apiLogin(username.trim(), password);
      navigateTo("/umumiy-dashboard", { replace: true });
    } catch (err) {
      setError(err.message || "Kirishda xatolik");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="loginShell">
      <div className="loginAmbient" aria-hidden="true">
        <span className="loginOrb loginOrbA" />
        <span className="loginOrb loginOrbB" />
        <span className="loginOrb loginOrbC" />
        <span className="loginOrb loginOrbD" />
        <span className="loginOrb loginOrbE" />
        <span className="loginMesh" />
        <span className="loginGrid" />
        <span className="loginRing loginRingOuter" />
        <span className="loginRing loginRingMid" />
        <span className="loginRing loginRingInner" />
      </div>

      <div className="loginStage">
        {/* Floating platform constellation around the centered form */}
        <div className="loginConstellation" aria-hidden="true">
          {PLATFORMS.map((platform, index) => (
            <motion.div
              key={platform.id}
              className={`loginFloatNode ${platform.id} node-${index + 1}`}
              initial={reduceMotion ? false : { opacity: 0, scale: 0.6 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={
                reduceMotion
                  ? { duration: 0 }
                  : { delay: 0.35 + index * 0.08, duration: 0.7, ease: easeOut }
              }
            >
              <PlatformMark platform={platform} size="lg" />
            </motion.div>
          ))}
        </div>

        <motion.section
          className="loginPanel"
          initial={reduceMotion ? false : { opacity: 0, y: 28, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={reduceMotion ? { duration: 0 } : { duration: 0.65, ease: easeOut, delay: 0.08 }}
        >
          <div className="loginPanelShine" aria-hidden="true" />

          <motion.div
            className="loginBrandBlock"
            initial={reduceMotion ? false : { opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={reduceMotion ? { duration: 0 } : { delay: 0.2, duration: 0.55, ease: easeOut }}
          >
            <span className="loginBrandMark" aria-hidden="true">
              <span className="loginBrandMarkGlow" />
              <Radio size={32} strokeWidth={2.1} />
            </span>
            <strong className="loginBrandName">MonitoringAI</strong>
          </motion.div>

          <motion.div
            className="loginPlatformStrip"
            aria-label="Monitoring platformalari"
            initial={reduceMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={reduceMotion ? { duration: 0 } : { delay: 0.35, duration: 0.5 }}
          >
            {PLATFORMS.map((platform, index) => (
              <motion.span
                key={`strip-${platform.id}`}
                initial={reduceMotion ? false : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={
                  reduceMotion
                    ? { duration: 0 }
                    : { delay: 0.4 + index * 0.06, duration: 0.4, ease: easeOut }
                }
              >
                <PlatformMark platform={platform} size="sm" />
              </motion.span>
            ))}
          </motion.div>

          <motion.div
            className="loginIntro"
            initial={reduceMotion ? false : { opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={reduceMotion ? { duration: 0 } : { delay: 0.28, duration: 0.5, ease: easeOut }}
          >
            <h1>Kirish</h1>
          </motion.div>

          <motion.form
            className="loginForm"
            onSubmit={handleSubmit}
            initial={reduceMotion ? false : { opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={reduceMotion ? { duration: 0 } : { delay: 0.36, duration: 0.5, ease: easeOut }}
          >
            <label className="field">
              <span>Email yoki login</span>
              <div className="inputWithIcon">
                <User size={17} aria-hidden />
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
              <div className="inputWithIcon hasPasswordToggle">
                <LockKeyhole size={17} strokeWidth={2} aria-hidden />
                <input
                  className="input"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                />
                <button
                  className="passwordToggle"
                  type="button"
                  onClick={() => setShowPassword((value) => !value)}
                  aria-label={showPassword ? "Parolni berkitish" : "Parolni ko'rsatish"}
                  aria-pressed={showPassword}
                  title={showPassword ? "Parolni berkitish" : "Parolni ko'rsatish"}
                >
                  {showPassword ? <EyeOff size={18} strokeWidth={2} /> : <Eye size={18} strokeWidth={2} />}
                </button>
              </div>
            </label>

            {error && (
              <motion.div
                className="errorBanner compact"
                initial={reduceMotion ? false : { opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25 }}
              >
                {error}
              </motion.div>
            )}

            <motion.button
              className="button primary solid fullButton loginSubmit"
              type="submit"
              disabled={loading}
              whileHover={reduceMotion ? undefined : { scale: 1.015, y: -1 }}
              whileTap={reduceMotion ? undefined : { scale: 0.985 }}
            >
              <span>{loading ? "Kirilmoqda..." : "Kirish"}</span>
              <ArrowRight size={17} />
            </motion.button>

            <p className="loginFooterLink">
              Akkount yo‘qmi?{" "}
              <a href="/register">Bepul ro‘yxatdan o‘tish</a>
            </p>
          </motion.form>
        </motion.section>
      </div>
    </main>
  );
}

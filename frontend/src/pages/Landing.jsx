/* Public landing page — what an anonymous visitor (and, critically, a Meta reviewer)
   sees at the root URL. Business verification and App Review both check that the
   website names the company, explains the product, states which data is used and why,
   and gives a working contact. A bare login screen fails all four. */

import { motion, useReducedMotion } from "motion/react";
import { MessageCircle, Youtube, Instagram, Sparkles, ShieldCheck, Bell, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { applyTheme, resolveTheme, toggleTheme } from "../theme";

const COMPANY = "Aviora AI";
const PRODUCT = "MonitoringAI";
const CONTACT_EMAIL = "amirhonhodisaliev@gmail.com";

const FEATURES = [
  {
    icon: MessageCircle,
    title: "Telegram monitoring",
    text: "Kanal va guruhlardagi postlar hamda kommentlar real vaqtda yig'iladi.",
    wide: true,
  },
  {
    icon: Youtube,
    title: "YouTube monitoring",
    text: "Kanal videolari va ulardagi kommentlar avtomatik kuzatiladi.",
    wide: false,
  },
  {
    icon: Instagram,
    title: "Instagram monitoring",
    text: "Biznes akkauntingiz postlari va kommentlari — o'zingiz ruxsat bergan holda.",
    wide: false,
  },
  {
    icon: Sparkles,
    title: "AI tahlil",
    text: "Har bir izoh kayfiyat va obro' xavfi bo'yicha baholanadi, qisqacha xulosa beriladi.",
    accent: true,
  },
  {
    icon: Bell,
    title: "Tezkor ogohlantirish",
    text: "Yuqori xavfli izoh topilsa, mas'ul xodimga Telegram orqali darhol xabar boradi.",
    wide: false,
  },
  {
    icon: ShieldCheck,
    title: "Ma'lumot xavfsizligi",
    text: "Ma'lumot sotilmaydi va reklama uchun ishlatilmaydi. Istalgan vaqtda o'chirish mumkin.",
    wide: false,
  },
];

function LandingHeroPreview() {
  return (
    <div className="landingHeroVisual" aria-hidden="true">
      <div className="landingHeroVisualGlow" />
      <div className="landingPreviewChrome">
        <i className="landingPreviewDot" />
        <i className="landingPreviewDot" />
        <i className="landingPreviewDot" />
        <span>Dashboard · real-time</span>
      </div>
      <div className="landingPreviewBody">
        <div className="landingPreviewNav">
          <i className="active" />
          <i />
          <i />
          <i />
        </div>
        <div className="landingPreviewMain">
          <div className="landingPreviewKpis">
            <article>
              <em>Mention</em>
              <strong>1 284</strong>
            </article>
            <article>
              <em>AI qamrov</em>
              <strong>92%</strong>
            </article>
            <article>
              <em>Yuqori risk</em>
              <strong>7</strong>
            </article>
          </div>
          <div className="landingPreviewChart">
            <svg viewBox="0 0 320 120" preserveAspectRatio="none">
              <path d="M8 88 C48 84, 72 40, 110 52 C148 64, 170 28, 210 36 C250 44, 280 18, 312 24" />
            </svg>
          </div>
          <div className="landingPreviewRows">
            <span>
              <b>@brand_channel</b>
              <em className="tone-neg">Salbiy · Yuqori</em>
            </span>
            <span>
              <b>YouTube comment</b>
              <em className="tone-pos">Ijobiy · Past</em>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export function Landing() {
  const reduceMotion = useReducedMotion();
  const [theme, setTheme] = useState(() => resolveTheme());

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  function handleThemeToggle() {
    setTheme(toggleTheme());
  }

  const reveal = reduceMotion
    ? {}
    : {
        initial: { opacity: 0, y: 18 },
        whileInView: { opacity: 1, y: 0 },
        viewport: { once: true, amount: 0.25 },
        transition: { duration: 0.28, ease: [0.16, 1, 0.3, 1] },
      };

  return (
    <div className="landingPage">
      <header className="legalHead">
        <a className="legalBrand" href="/">{PRODUCT}</a>
        <nav className="legalNav">
          <a href="/privacy">Maxfiylik</a>
          <a href="/terms">Shartlar</a>
          <a href="/data-deletion">Ma'lumotni o'chirish</a>
          <button
            className="themeToggle"
            type="button"
            onClick={handleThemeToggle}
            aria-label={theme === "dark" ? "Yorug' rejim" : "Qorong'u rejim"}
            title={theme === "dark" ? "Yorug' rejim" : "Qorong'u rejim"}
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </button>
          <a className="landingLoginLink" href="/login">Kirish</a>
        </nav>
      </header>

      <main className="landingBody">
        <section className="landingHero">
          <motion.div className="landingHeroCopy" {...(reduceMotion ? {} : {
            initial: { opacity: 0, y: 16 },
            animate: { opacity: 1, y: 0 },
            transition: { duration: 0.3, ease: [0.16, 1, 0.3, 1] },
          })}>
            <span className="landingEyebrow">{COMPANY}</span>
            <h1>Brendingiz haqida nima deyilayotganini bir joyda ko'ring</h1>
            <p>
              {PRODUCT} Telegram, YouTube va Instagram izohlarini yig'ib, kayfiyat va obro'
              xavfini AI bilan tahlil qiladi. Salbiy signal paydo bo'lishi bilan jamoa xabardor bo'ladi.
            </p>
            <div className="landingCtaRow">
              <a className="button primary landingCta" href="/login">Dashboardga kirish</a>
              <a className="landingCtaSecondary" href="#how-it-works">Qanday ishlaydi</a>
            </div>
          </motion.div>
          <motion.div {...(reduceMotion ? {} : {
            initial: { opacity: 0, y: 20 },
            animate: { opacity: 1, y: 0 },
            transition: { duration: 0.32, delay: 0.06, ease: [0.16, 1, 0.3, 1] },
          })}>
            <LandingHeroPreview />
          </motion.div>
        </section>

        <motion.section className="landingFeatures" {...reveal}>
          {FEATURES.map(({ icon: Icon, title, text, wide, accent }) => (
            <article
              className={`landingCard${wide ? " wide" : ""}${accent ? " accent" : ""}`}
              key={title}
            >
              <span className="landingCardIcon">
                <Icon size={18} />
              </span>
              <strong>{title}</strong>
              <span>{text}</span>
            </article>
          ))}
        </motion.section>

        <motion.section className="landingSteps" id="how-it-works" {...reveal}>
          <h2>Qanday ishlaydi</h2>
          <ol>
            <li><strong>Ulaysiz.</strong> Brendingizni kiritasiz va kuzatiladigan kanal yoki akkauntlarni qo'shasiz.</li>
            <li><strong>Yig'ladi.</strong> Tizim yangi post va izohlarni avtomatik, uzluksiz to'playdi.</li>
            <li><strong>Tahlil qiladi.</strong> Har bir izoh AI orqali baholanadi: ijobiy/salbiy, xavf darajasi, tavsiya etilgan javob.</li>
            <li><strong>Ogohlantiradi.</strong> Xavfli signal topilsa, mas'ul xodimga darhol xabar yuboriladi.</li>
          </ol>
        </motion.section>

        <motion.section className="landingAbout" {...reveal}>
          <h2>About {PRODUCT} (English)</h2>
          <p>
            {PRODUCT}, operated by {COMPANY}, is a social listening platform for brands. With the account
            owner's explicit consent, it reads the comments left on the brand's own social media accounts
            and analyses them for sentiment and reputational risk, so the brand's team can respond quickly.
          </p>
          <p>
            <strong>Instagram data usage.</strong> After the business owner authorises us through Business
            Login for Instagram, we read the connected professional account's own media and the comments on
            it. Comments are analysed and displayed only in that customer's private dashboard. We never sell
            data, never use it for advertising, and delete it when the account is disconnected. See our{" "}
            <a href="/privacy">Privacy Policy</a> and <a href="/data-deletion">Data Deletion</a> pages.
          </p>
        </motion.section>

        <motion.section className="landingContact" {...reveal}>
          <h2>Aloqa / Contact</h2>
          <p>
            <strong>{COMPANY}</strong><br />
            Email: <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a><br />
            Veb: <a href="https://monitoring.avioraai.uz">monitoring.avioraai.uz</a>
          </p>
        </motion.section>
      </main>

      <footer className="landingFooter">
        <span>© 2026 {COMPANY}</span>
        <nav className="legalNav">
          <a href="/privacy">Privacy</a>
          <a href="/terms">Terms</a>
          <a href="/data-deletion">Data deletion</a>
        </nav>
      </footer>
    </div>
  );
}

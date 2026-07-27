/* Official marketing site at /. Dashboard lives at /umumiy-dashboard. */

import { motion, useReducedMotion } from "motion/react";
import {
  ArrowUpRight,
  Bell,
  Check,
  ExternalLink,
  Globe2,
  Link2,
  Mail,
  Menu,
  MessageCircle,
  Moon,
  Radio,
  ShieldCheck,
  Sparkles,
  Sun,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { isAuthed, clearApiCache } from "../api/client";
import {
  LandingBarsChart,
  LandingDonutChart,
  LandingGaugeChart,
  LandingPreviewChart,
  LandingSparkChart,
  useLandingLiveKpis,
} from "../components/TrendChart";
import { UI_LANGUAGE_KEY } from "../i18n";
import { applyTheme, resolveTheme, toggleTheme } from "../theme";

const COMPANY = "Aviora AI";
const PRODUCT = "MonitoringAI";
const CONTACT_EMAIL = "avioraai1@gmail.com";
const SITE_URL = "https://monitoring.avioraai.uz";
const SITE_HOST = "monitoring.avioraai.uz";

const VERTEX_COST_PER_MENTION = 0.025;
const PLATFORM_BASE_USD = 70;

const PLANS = [
  {
    id: "start",
    name: "Start",
    mentions: 2000,
    blurbKey: "Kichik jamoalar va bitta brend uchun.",
    featureKeys: ["Telegram + YouTube", "AI kayfiyat tahlili", "Email qo'llab-quvvatlash"],
    popular: false,
  },
  {
    id: "growth",
    name: "Growth",
    mentions: 6000,
    blurbKey: "O'sayotgan brendlar va PR jamoalari.",
    featureKeys: ["Barcha platformalar", "Tezkor Telegram alert", "Risk darajasi + tavsiya"],
    popular: true,
  },
  {
    id: "business",
    name: "Business",
    mentions: 15000,
    blurbKey: "Ko'p manba, yuqori hajmli monitoring.",
    featureKeys: ["Ko'p brend profili", "Ustuvor signal inbox", "Tezroq javob SLA"],
    popular: false,
  },
  {
    id: "scale",
    name: "Scale",
    mentions: 40000,
    blurbKey: "Katta tarmoq va agentliklar uchun.",
    featureKeys: ["Yuqori limit", "Maxsus sozlash", "Prioritet qo'llab-quvvatlash"],
    popular: false,
  },
].map((plan) => {
  const vertexCost = Math.round(plan.mentions * VERTEX_COST_PER_MENTION);
  return { ...plan, vertexCost, price: vertexCost + PLATFORM_BASE_USD };
});

const HOW_STEPS = [
  {
    icon: Link2,
    titleKey: "Ulang",
    textKey: "Brend va rasmiy kanallarni qo'shasiz.",
    tone: "a",
    visual: "link",
    hintKey: "Source setup",
  },
  {
    icon: Radio,
    titleKey: "Yig'iladi",
    textKey: "Post va izohlar avtomatik oqadi.",
    tone: "b",
    visual: "stream",
    hintKey: "Live ingest",
  },
  {
    icon: Sparkles,
    titleKey: "Tahlil",
    textKey: "Vertex AI kayfiyat va xavfni baholaydi.",
    tone: "c",
    visual: "ai",
    hintKey: "Vertex AI",
  },
  {
    icon: Bell,
    titleKey: "Ogohlantirish",
    textKey: "Muhim signal darhol jamoaga boradi.",
    tone: "d",
    visual: "alert",
    hintKey: "Telegram",
  },
];

const FEATURES = [
  {
    icon: MessageCircle,
    titleKey: "4 platforma",
    textKey: "Telegram, YouTube, Instagram, Facebook",
    wide: true,
    visual: "platforms",
    chips: ["TG", "YT", "IG", "FB"],
  },
  {
    icon: Sparkles,
    titleKey: "AI tahlil",
    textKey: "Kayfiyat, xavf, qisqa xulosa",
    accent: true,
    visual: "ai",
  },
  {
    icon: Bell,
    titleKey: "Tezkor alert",
    textKey: "Yuqori risk - darhol xabar",
    visual: "pulse",
  },
  {
    icon: ShieldCheck,
    titleKey: "Xavfsizlik",
    textKey: "Ma'lumot sotilmaydi, o'chirish mumkin",
    visual: "shield",
  },
];

const ABOUT_METRICS = [
  { k: "Vertex AI", vKey: "Chuqur tahlil", tone: "a" },
  { k: "Live", vKey: "Uzluksiz oqim", tone: "b" },
  { k: "Alert", vKey: "Telegram xabar", tone: "c" },
];

/* Real brand domains + local logo assets under /images/clients */
const CLIENTS = [
  { name: "Uzum", domain: "uzum.uz", logo: "/images/clients/uzum.png" },
  { name: "Ucell", domain: "ucell.uz", logo: "/images/clients/ucell.png" },
  { name: "Beeline", domain: "beeline.uz", logo: "/images/clients/beeline.png" },
  { name: "Ipoteka Bank", domain: "ipotekabank.uz", logo: "/images/clients/ipoteka.png" },
  { name: "Hamkorbank", domain: "hamkorbank.uz", logo: "/images/clients/hamkorbank.png" },
  { name: "Artel", domain: "artelgroup.org", logo: "/images/clients/artel.png" },
  { name: "Korzinka", domain: "korzinka.uz", logo: "/images/clients/korzinka.png" },
  { name: "Click", domain: "click.uz", logo: "/images/clients/click.png" },
  { name: "Payme", domain: "payme.uz", logo: "/images/clients/payme.png" },
  { name: "Anor Bank", domain: "anorbank.uz", logo: "/images/clients/anorbank.png" },
  { name: "Texnomart", domain: "texnomart.uz", logo: "/images/clients/texnomart.png" },
  { name: "Asaxiy", domain: "asaxiy.uz", logo: "/images/clients/asaxiy.png" },
  { name: "EVOS", domain: "evos.uz", logo: "/images/clients/evos.png" },
  { name: "Express24", domain: "express24.uz", logo: "/images/clients/express24.png" },
  { name: "Olcha", domain: "olcha.uz", logo: "/images/clients/olcha.png" },
  { name: "Humans", domain: "humans.uz", logo: "/images/clients/humans.png" },
];

const NAV_LINKS = [
  { href: "#haqida", labelKey: "Loyiha" },
  { href: "#qanday-ishlaydi", labelKey: "Qanday ishlaydi" },
  { href: "#mijozlar", labelKey: "Mijozlar" },
  { href: "#tariflar", labelKey: "Tariflar" },
  { href: "#aloqa", labelKey: "Aloqa" },
];

function formatUsd(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatMentions(value, language = "uz") {
  const locale = language === "ru" ? "ru-RU" : language === "en" ? "en-US" : "uz-UZ";
  return new Intl.NumberFormat(locale).format(value);
}

function clientInitials(name) {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function faviconUrl(domain) {
  return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=128`;
}

function ClientLogo({ name, domain, logo }) {
  const [src, setSrc] = useState(logo || faviconUrl(domain));
  const [stage, setStage] = useState(0);
  const [failed, setFailed] = useState(false);

  function handleError() {
    if (stage === 0) {
      setStage(1);
      setSrc(faviconUrl(domain));
      return;
    }
    setFailed(true);
  }

  if (failed) {
    return (
      <span className="landingClientFallback" aria-hidden="true">
        {clientInitials(name)}
      </span>
    );
  }

  return (
    <img
      className="landingClientLogo"
      src={src}
      alt=""
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      onError={handleError}
    />
  );
}

function ClientsCarousel({ reduceMotion, ariaLabel }) {
  const loop = [...CLIENTS, ...CLIENTS];

  return (
    <div className={`landingMarquee${reduceMotion ? " isStatic" : ""}`} aria-label={ariaLabel}>
      <div className="landingMarqueeFade left" aria-hidden="true" />
      <div className="landingMarqueeFade right" aria-hidden="true" />
      <div className="landingMarqueeTrack">
        {loop.map((client, index) => (
          <div className="landingClientChip" key={`${client.name}-${index}`} title={client.name}>
            <span className="landingClientLogoWrap">
              <ClientLogo name={client.name} domain={client.domain} logo={client.logo} />
            </span>
            <span className="landingClientName">{client.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function LandingHeroPreview() {
  const { t, i18n } = useTranslation();
  const live = useLandingLiveKpis();
  const language = i18n.resolvedLanguage || i18n.language || "uz";
  const mentionLabel = formatMentions(live.mentions, language);

  return (
    <div className="landingHeroVisual landingHeroVisual--live">
      <div className="landingHeroVisualAura" aria-hidden="true" />
      <div className="landingPreviewChrome">
        <span className="brandPulse" />
        <span>
          {PRODUCT} · {t("live")}
        </span>
        <em className="landingLiveDot">
          <i />
          {t("online")}
        </em>
      </div>
      <div className="landingPreviewBody">
        <div className="landingPreviewNav" aria-hidden="true">
          <i className="active" />
          <i />
          <i />
          <i />
        </div>
        <div className="landingPreviewMain">
          <div className="landingPreviewKpis">
            <article className="landingKpiLive">
              <span>{t("Mention")}</span>
              <strong>{mentionLabel}</strong>
            </article>
            <article className="tone-ai landingKpiLive">
              <span>{t("AI qamrov")}</span>
              <strong>{live.coverage}%</strong>
            </article>
            <article className="tone-risk landingKpiLive">
              <span>{t("Yuqori risk")}</span>
              <strong>{live.risk}</strong>
              <div className="landingPreviewSpark">
                <LandingSparkChart height={28} />
              </div>
            </article>
          </div>

          <div className="landingPreviewCharts">
            <div className="landingChartTile landingChartTileWave">
              <header>
                <span>{t("Trend")}</span>
                <em>+{live.trendPct}%</em>
              </header>
              <LandingPreviewChart height={108} />
            </div>
            <div className="landingChartTile landingChartTileGauge">
              <header>
                <span>{t("Brand score")}</span>
              </header>
              <LandingGaugeChart value={92} max={100} height={132} label={t("AI score")} tone="accent" />
            </div>
            <div className="landingChartTile landingChartTileDonut">
              <header>
                <span>{t("Kayfiyat")}</span>
              </header>
              <LandingDonutChart height={92} />
            </div>
            <div className="landingChartTile landingChartTileBars">
              <header>
                <span>{t("Platformalar")}</span>
              </header>
              <LandingBarsChart height={92} />
            </div>
          </div>

          <div className="landingPreviewRows">
            <span>
              <b>@brand_channel</b>
              <em className="tone-neg">{t("Salbiy · Yuqori")}</em>
            </span>
            <span>
              <b>{t("YouTube comment")}</b>
              <em className="tone-pos">{t("Ijobiy · Past")}</em>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function scrollToHash(hash) {
  if (!hash || hash === "#") return;
  const id = hash.replace(/^#/, "");
  const el = document.getElementById(id);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "start" });
}

/** Spotlight follows cursor via CSS vars (no React re-render). */
function SpotlightCard({ as: Tag = "article", className = "", children, ...props }) {
  const ref = useRef(null);

  function onMove(event) {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${event.clientX - rect.left}px`);
    el.style.setProperty("--my", `${event.clientY - rect.top}px`);
  }

  return (
    <Tag ref={ref} className={`landingSpot ${className}`.trim()} onMouseMove={onMove} {...props}>
      <span className="landingSpotGlow" aria-hidden="true" />
      {children}
    </Tag>
  );
}

function Reveal({ children, className = "", delay = 0, y = 22, reduceMotion }) {
  if (reduceMotion) return <div className={className}>{children}</div>;
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.48, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  );
}

function RevealItem({ children, className = "", index = 0, reduceMotion, as: Tag = "div" }) {
  if (reduceMotion) return <Tag className={className}>{children}</Tag>;
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.25 }}
      transition={{
        duration: 0.42,
        delay: 0.05 + index * 0.05,
        ease: [0.16, 1, 0.3, 1],
      }}
    >
      {Tag === "div" ? children : <Tag className="landingRevealInner">{children}</Tag>}
    </motion.div>
  );
}

export function Landing() {
  const { t, i18n } = useTranslation();
  const reduceMotion = useReducedMotion();
  const [theme, setTheme] = useState(() => resolveTheme());
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const authed = isAuthed();
  const language = i18n.resolvedLanguage || i18n.language || "uz";

  useEffect(() => {
    // Paint only — toggleTheme() is what persists user choice
    applyTheme(theme, { persist: false });
  }, [theme]);

  useEffect(() => {
    if (window.location.hash) {
      requestAnimationFrame(() => scrollToHash(window.location.hash));
    }
  }, []);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    function onResize() {
      if (window.innerWidth > 900) setMenuOpen(false);
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    document.body.style.overflow = menuOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [menuOpen]);

  function handleThemeToggle() {
    setTheme(toggleTheme());
  }

  function changeLanguage(nextLanguage) {
    clearApiCache();
    window.localStorage.setItem(UI_LANGUAGE_KEY, nextLanguage);
    i18n.changeLanguage(nextLanguage);
  }

  function handleNavClick(event, href) {
    if (!href.startsWith("#")) return;
    event.preventDefault();
    setMenuOpen(false);
    const url = new URL(window.location.href);
    url.hash = href;
    window.history.pushState(null, "", url);
    scrollToHash(href);
  }

  return (
    <div className={`landingPage${menuOpen ? " isMenuOpen" : ""}`}>
      <div className="landingBg" aria-hidden="true">
        <span className="landingOrb landingOrbA" />
        <span className="landingOrb landingOrbB" />
        <span className="landingOrb landingOrbC" />
        <span className="landingMesh" />
        <span className="landingGridFx" />
      </div>

      <header className={`landingHead${scrolled || menuOpen ? " isScrolled" : ""}`}>
        <a className="landingBrand brandMark" href="/">
          <span className="brandPulse" />
          <span className="brandText">{PRODUCT}</span>
        </a>
        <nav className="landingNav" aria-label={t("Asosiy bo'limlar")}>
          {NAV_LINKS.map((link) => (
            <a key={link.href} href={link.href} onClick={(e) => handleNavClick(e, link.href)}>
              {t(link.labelKey)}
            </a>
          ))}
        </nav>
        <div className="landingHeadActions">
          <div className="landingLangSwitch landingLangSwitch--desktop" title={t("Interfeys tili")}>
            {["uz", "ru", "en"].map((item) => (
              <button
                key={item}
                type="button"
                className={language === item ? "active" : ""}
                aria-pressed={language === item}
                onClick={() => changeLanguage(item)}
              >
                {item.toUpperCase()}
              </button>
            ))}
          </div>
          <button
            className="themeToggle"
            type="button"
            onClick={handleThemeToggle}
            aria-label={theme === "dark" ? t("Yorug' rejim") : t("Qorong'u rejim")}
            title={theme === "dark" ? t("Yorug' rejim") : t("Qorong'u rejim")}
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </button>
          <a className="button primary solid landingHeadCta" href={authed ? "/umumiy-dashboard" : "/register"}>
            {authed ? t("Dashboard") : t("Bepul boshlash")}
          </a>
          <button
            className="landingMenuToggle"
            type="button"
            aria-expanded={menuOpen}
            aria-controls="landing-mobile-nav"
            aria-label={menuOpen ? t("Yopish") : t("Menyu")}
            onClick={() => setMenuOpen((open) => !open)}
          >
            {menuOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
      </header>

      <div
        className={`landingMobilePanel${menuOpen ? " isOpen" : ""}`}
        id="landing-mobile-nav"
        hidden={!menuOpen}
      >
        <nav className="landingMobileNav" aria-label={t("Asosiy bo'limlar")}>
          {NAV_LINKS.map((link) => (
            <a key={link.href} href={link.href} onClick={(e) => handleNavClick(e, link.href)}>
              {t(link.labelKey)}
            </a>
          ))}
        </nav>
        <div className="landingMobileMeta">
          <div className="landingLangSwitch" title={t("Interfeys tili")}>
            {["uz", "ru", "en"].map((item) => (
              <button
                key={item}
                type="button"
                className={language === item ? "active" : ""}
                aria-pressed={language === item}
                onClick={() => changeLanguage(item)}
              >
                {item.toUpperCase()}
              </button>
            ))}
          </div>
          <a
            className="button primary solid landingMobileCta"
            href={authed ? "/umumiy-dashboard" : "/register"}
            onClick={() => setMenuOpen(false)}
          >
            {authed ? t("Dashboard") : t("Bepul boshlash")}
          </a>
        </div>
      </div>
      {menuOpen ? (
        <button
          className="landingMobileScrim"
          type="button"
          aria-label={t("Yopish")}
          onClick={() => setMenuOpen(false)}
        />
      ) : null}

      <main className="landingBody">
        <section className="landingHero">
          <motion.div
            className="landingHeroCopy"
            {...(reduceMotion
              ? {}
              : {
                  initial: { opacity: 0, y: 12 },
                  animate: { opacity: 1, y: 0 },
                  transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] },
                })}
          >
            <span className="landingEyebrow">
              <span className="landingEyebrowDot" />
              {COMPANY}
            </span>
            <h1>{t("Brendingiz haqida nima deyilayotganini bir joyda ko'ring")}</h1>
            <p>
              {t(
                "Telegram, YouTube, Instagram va Facebook izohlarini yig'ib, Vertex AI bilan tahlil qiladi. Xavfli signal paydo bo'lishi bilan jamoa xabardor bo'ladi.",
              )}
            </p>
            <div className="landingCtaRow">
              <a className="button primary landingCtaPrimary" href={authed ? "/umumiy-dashboard" : "/register"}>
                {authed ? t("Dashboardga o'tish") : t("Bepul boshlash")}
                <ArrowUpRight size={16} />
              </a>
              <a
                className="button landingCtaGhost"
                href="#qanday-ishlaydi"
                onClick={(e) => handleNavClick(e, "#qanday-ishlaydi")}
              >
                {t("Qanday ishlaydi")}
              </a>
            </div>
            <div className="landingHeroStats" aria-hidden="true">
              <span>
                <b>4</b> {t("platforma")}
              </span>
              <span>
                <b>AI</b> {t("real-time")}
              </span>
              <span>
                <b>24/7</b> {t("signal")}
              </span>
            </div>
          </motion.div>
          <motion.div
            className="landingHeroVisualWrap"
            {...(reduceMotion
              ? {}
              : {
                  initial: { opacity: 0, y: 14 },
                  animate: { opacity: 1, y: 0 },
                  transition: { duration: 0.45, delay: 0.05, ease: [0.16, 1, 0.3, 1] },
                })}
          >
            <div className="landingHeroFloat" aria-hidden="true" />
            <LandingHeroPreview />
          </motion.div>
        </section>

        <section className="landingSection landingAbout" id="haqida">
          <div className="landingAboutScene" aria-hidden="true">
            <span className="landingAboutBlob landingAboutBlobA" />
            <span className="landingAboutBlob landingAboutBlobB" />
            <span className="landingAboutBlob landingAboutBlobC" />
            <span className="landingAboutNoise" />
          </div>

          <div className="landingAboutShell">
            <Reveal className="landingAboutMain" reduceMotion={reduceMotion} y={36}>
              <div className="landingAboutFrame">
                <span className="landingAboutFrameBorder" aria-hidden="true" />
                <SpotlightCard as="div" className="landingAboutMainInner">
                  <div className="landingAboutTop">
                    <span className="landingAboutPill">
                      <i />
                      {t("Loyiha")}
                    </span>
                    <span className="landingAboutLive">
                      <em />
                      {t("Real-time")}
                    </span>
                  </div>

                  <h2>
                    {t("Ijtimoiy eshitish")}
                    <span className="landingAboutTitleLine">{t("brend jamoasi uchun")}</span>
                  </h2>

                  <p className="landingAboutLead">
                    {t(
                      "MonitoringAI - Aviora AI tomonidan ishlab chiqilgan monitoring platformasi. Brendingiz haqidagi izohlarni yig'adi, kayfiyat va obro' xavfini AI bilan baholaydi, muhim signallarni darhol yetkazadi.",
                    )}
                  </p>
                  <p>
                    {t(
                      "Maqsad oddiy: jamoa kechikmasdan javob bersin, salbiy to'lqin o'sib ketmasin, ijobiy fikrlar esa o'z vaqtida ko'rinsin.",
                    )}
                  </p>

                  <div className="landingAboutSignal" aria-hidden="true">
                    <span />
                    <span />
                    <span />
                    <span />
                    <span />
                  </div>

                  <div className="landingAboutMetrics">
                    {ABOUT_METRICS.map((m) => (
                      <div className={`landingAboutMetric tone-${m.tone}`} key={m.k}>
                        <strong>{m.k}</strong>
                        <span>{t(m.vKey)}</span>
                      </div>
                    ))}
                  </div>
                </SpotlightCard>
              </div>
            </Reveal>

            <div className="landingBento">
              {FEATURES.map(({ icon: Icon, titleKey, textKey, wide, accent, visual, chips }, index) => (
                <RevealItem
                  key={titleKey}
                  index={index}
                  reduceMotion={reduceMotion}
                  className={wide ? "landingBentoWideWrap" : ""}
                >
                  <SpotlightCard
                    className={`landingBentoCard visual-${visual}${wide ? " isWide" : ""}${accent ? " isAccent" : ""}`}
                  >
                    <div className="landingBentoCardTop">
                      <span className="landingBentoIcon">
                        <Icon size={18} />
                      </span>
                      {visual === "pulse" ? <span className="landingBentoPulse" aria-hidden="true" /> : null}
                    </div>
                    <strong>{t(titleKey)}</strong>
                    <span className="landingBentoText">{t(textKey)}</span>

                    {visual === "platforms" && chips ? (
                      <div className="landingBentoPlatforms" aria-hidden="true">
                        {chips.map((chip) => (
                          <em key={chip}>{chip}</em>
                        ))}
                      </div>
                    ) : null}

                    {visual === "ai" ? (
                      <div className="landingBentoAiWave" aria-hidden="true">
                        <i />
                        <i />
                        <i />
                        <i />
                        <i />
                      </div>
                    ) : null}

                    {visual === "shield" ? (
                      <div className="landingBentoShieldRing" aria-hidden="true" />
                    ) : null}

                    <i className="landingCardShine" aria-hidden="true" />
                  </SpotlightCard>
                </RevealItem>
              ))}
            </div>
          </div>
        </section>

        <section className="landingSection landingHow" id="qanday-ishlaydi">
          <div className="landingHowScene" aria-hidden="true">
            <span className="landingHowBlob landingHowBlobA" />
            <span className="landingHowBlob landingHowBlobB" />
          </div>

          <Reveal className="landingSectionHead landingHowHead" reduceMotion={reduceMotion}>
            <span className="landingHowEyebrow">
              <i />
              {t("Pipeline")}
            </span>
            <h2>{t("Qanday ishlaydi")}</h2>
            <p>{t("To'rt qisqa qadam. Batafsil sozlash dashboard ichida.")}</p>
          </Reveal>

          <div className="landingHowStage">
            <div className="landingHowRail">
              <div className="landingHowTrack" aria-hidden="true">
                <span className="landingHowTrackGlow" />
                <span className="landingHowTrackPacket" />
              </div>

              {HOW_STEPS.map(({ icon: Icon, titleKey, textKey, tone, visual, hintKey }, index) => (
                <RevealItem key={titleKey} index={index} reduceMotion={reduceMotion} className="landingHowStepWrap">
                  <SpotlightCard
                    className={`landingHowCard tone-${tone} visual-${visual}`}
                    style={{ "--how-i": index }}
                  >
                    <div className="landingHowNode" aria-hidden="true">
                      <span>{String(index + 1).padStart(2, "0")}</span>
                    </div>

                    <div className="landingHowTop">
                      <span className="landingHowHint">{t(hintKey)}</span>
                      <span className="landingHowIcon">
                        <Icon size={18} />
                      </span>
                    </div>

                    <strong>{t(titleKey)}</strong>
                    <span className="landingHowText">{t(textKey)}</span>

                    {visual === "link" ? (
                      <div className="landingHowViz landingHowVizLink" aria-hidden="true">
                        <em />
                        <i />
                        <em />
                      </div>
                    ) : null}

                    {visual === "stream" ? (
                      <div className="landingHowViz landingHowVizStream" aria-hidden="true">
                        <span />
                        <span />
                        <span />
                        <span />
                      </div>
                    ) : null}

                    {visual === "ai" ? (
                      <div className="landingHowViz landingHowVizAi" aria-hidden="true">
                        <i />
                        <i />
                        <i />
                        <i />
                        <i />
                      </div>
                    ) : null}

                    {visual === "alert" ? (
                      <div className="landingHowViz landingHowVizAlert" aria-hidden="true">
                        <em />
                        <i />
                      </div>
                    ) : null}

                    <i className="landingCardShine" aria-hidden="true" />
                  </SpotlightCard>
                </RevealItem>
              ))}
            </div>
          </div>
        </section>

        <section className="landingSection landingClients" id="mijozlar">
          <Reveal className="landingSectionHead center" reduceMotion={reduceMotion} y={20}>
            <h2>{t("Kimlar foydalanmoqda")}</h2>
            <p>{t("O'zbekistondagi yirik brendlar uchun monitoring yondashuvi.")}</p>
          </Reveal>
          <Reveal reduceMotion={reduceMotion} delay={0.08} y={16}>
            <div className="landingClientsStage">
              <ClientsCarousel reduceMotion={reduceMotion} ariaLabel={t("Mijozlar brendlari")} />
            </div>
          </Reveal>
          <p className="landingClientsNote">{t("Namuna brendlar ro'yxati - marketing demo uchun.")}</p>
        </section>

        <section className="landingSection landingPricing" id="tariflar">
          <Reveal className="landingSectionHead" reduceMotion={reduceMotion}>
            <h2>{t("Sizga mos reja")}</h2>
            <p>
              {t(
                "Monitoring hajmi va jamoa ehtiyojiga qarab tanlang. AI tahlil, alertlar va asosiy imkoniyatlar paket ichida.",
              )}
            </p>
          </Reveal>
          <div className="landingPricingGrid">
            {PLANS.map((plan, index) => (
              <RevealItem key={plan.id} index={index} reduceMotion={reduceMotion}>
                <SpotlightCard className={`landingPlanCard${plan.popular ? " isPopular" : ""}`}>
                  {plan.popular ? <span className="landingPlanBadge">{t("Tavsiya")}</span> : null}
                  <header>
                    <h3>{plan.name}</h3>
                    <p>{t(plan.blurbKey)}</p>
                  </header>
                  <div className="landingPlanPrice">
                    <strong>{formatUsd(plan.price)}</strong>
                    <span>{t("/ oy")}</span>
                  </div>
                  <div className="landingPlanMeta">
                    <span>
                      <b>{formatMentions(plan.mentions, language)}</b> {t("mention / oy")}
                    </span>
                    <span className="landingPlanBreakdown">
                      {t("AI tahlil va monitoring paketi")}
                    </span>
                  </div>
                  <ul>
                    {plan.featureKeys.map((feature) => (
                      <li key={feature}>
                        <Check size={15} />
                        {t(feature)}
                      </li>
                    ))}
                  </ul>
                  <a
                    className={`button${plan.popular ? " primary" : ""} landingPlanCta`}
                    href={authed ? "/umumiy-dashboard" : `/register?plan=${plan.id}`}
                  >
                    {authed ? t("Dashboard") : t("Tanlash")}
                  </a>
                  <i className="landingCardShine" aria-hidden="true" />
                </SpotlightCard>
              </RevealItem>
            ))}
          </div>
        </section>

        <section className="landingSection landingContact" id="aloqa">
          <Reveal className="landingSectionHead" reduceMotion={reduceMotion}>
            <h2>{t("Aloqa")}</h2>
            <p>{t("Savol, demo yoki hamkorlik uchun yozing — ish kunida javob beramiz.")}</p>
          </Reveal>
          <Reveal reduceMotion={reduceMotion} y={24}>
            <div className="landingContactPanel">
              <div className="landingContactMain">
                <p className="landingContactKicker">{COMPANY}</p>
                <h3 className="landingContactTitle">{t("Biz bilan bog'laning")}</h3>
                <p className="landingContactLead">
                  {t("MonitoringAI bo'yicha demo, integratsiya yoki maxsus tarif so'rovi qoldiring.")}
                </p>
                <div className="landingContactActions">
                  <a className="button primary solid landingContactCta" href={`mailto:${CONTACT_EMAIL}`}>
                    <Mail size={16} aria-hidden />
                    {t("Email yozish")}
                  </a>
                  <a className="button landingContactSecondary" href={authed ? "/umumiy-dashboard" : "/register"}>
                    {authed ? t("Dashboard") : t("Bepul boshlash")}
                    <ArrowUpRight size={15} aria-hidden />
                  </a>
                </div>
              </div>

              <aside className="landingContactAside" aria-label={t("Aloqa ma'lumotlari")}>
                <div className="landingContactRow">
                  <span className="landingContactIcon" aria-hidden>
                    <Mail size={16} />
                  </span>
                  <div>
                    <span className="landingContactLabel">{t("Email")}</span>
                    <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
                  </div>
                </div>
                <div className="landingContactRow">
                  <span className="landingContactIcon" aria-hidden>
                    <Globe2 size={16} />
                  </span>
                  <div>
                    <span className="landingContactLabel">{t("Veb-sayt")}</span>
                    <a href={SITE_URL} target="_blank" rel="noreferrer">
                      {SITE_HOST}
                      <ExternalLink size={12} aria-hidden />
                    </a>
                  </div>
                </div>
                <div className="landingContactMeta">
                  <span>{PRODUCT}</span>
                  <span aria-hidden>·</span>
                  <span>{COMPANY}</span>
                </div>
                <nav className="landingContactLegal" aria-label={t("Huquqiy")}>
                  <a href="/privacy">{t("Maxfiylik")}</a>
                  <a href="/terms">{t("Shartlar")}</a>
                  <a href="/data-deletion">{t("Ma'lumotni o'chirish")}</a>
                </nav>
              </aside>
            </div>
          </Reveal>
        </section>
      </main>

      <footer className="landingFooter">
        <div className="landingFooterInner">
          <div className="landingFooterBrand">
            <strong>{PRODUCT}</strong>
            <span>
              © 2026 {COMPANY}. {t("Barcha huquqlar himoyalangan.")}
            </span>
          </div>
          <nav className="landingFooterNav" aria-label="Footer">
            <a href="/privacy">{t("Maxfiylik")}</a>
            <a href="/terms">{t("Shartlar")}</a>
            <a href="/data-deletion">{t("Ma'lumotni o'chirish")}</a>
            <a href={`mailto:${CONTACT_EMAIL}`}>{t("Aloqa")}</a>
            <a href={authed ? "/umumiy-dashboard" : "/login"}>{authed ? t("Dashboard") : t("Kirish")}</a>
            {!authed ? <a href="/register">{t("Bepul boshlash")}</a> : null}
          </nav>
        </div>
      </footer>
    </div>
  );
}

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  AlertCircle,
  Brain,
  CalendarClock,
  CheckCircle2,
  ExternalLink,
  Facebook,
  Globe2,
  Hash,
  Instagram,
  Link2,
  ListChecks,
  LogOut,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Save,
  ShieldCheck,
  Sparkles,
  Tags,
  Target,
  Trash2,
  UserCog,
  X,
} from "lucide-react";
import {
  endpoints,
  isBrandUnlocked,
  isSuperAdmin,
  logout,
  markBrandUnlocked,
  readAdminSession,
  readSelectedBrandId,
  resolveSelectedBrandId,
  saveAdminSession,
  saveSelectedBrandId,
  unlockBrand,
} from "../api/client";
import { TelegramIcon, YouTubeIcon } from "../components/BrandIcons";
import DeleteSourceModal from "../components/DeleteSourceModal";
import { PageHeader } from "../components/PageHeader";
import { Sidebar } from "../components/Sidebar";
import { SmartSelect } from "../components/SmartSelect";
import { TelegramConnectionForm } from "../components/TelegramConnectionForm";
import { translateUiText } from "../i18n";
import {
  canonicalOfficialChannelSourceRef,
  officialChannelFieldsFromSource,
  officialChannelRef,
} from "../youtubeChannelRef";

const platformTabs = [
  {
    key: "telegram",
    label: "Telegram",
    icon: TelegramIcon,
    tone: "telegram",
    description: "Rasmiy kanal, guruh, linked discussion va bot source'lari.",
  },
  {
    key: "youtube",
    label: "YouTube",
    icon: YouTubeIcon,
    tone: "youtube",
    description: "Rasmiy kanal, video source, hashtag va comment oqimi.",
  },
  {
    key: "instagram",
    label: "Instagram",
    icon: Instagram,
    tone: "instagram",
    description: "Instagram Business akkaunt, comment va @mention oqimi.",
  },
  {
    key: "facebook",
    label: "Facebook",
    icon: Facebook,
    tone: "facebook",
    description: "Facebook Page token, comment va reply oqimi.",
  },
];

function todayInputValue() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 10);
}

function dateInputValue(value) {
  if (!value) return todayInputValue();
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return todayInputValue();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 10);
}

function csvLine(values) {
  return values.map((value) => `"${String(value || "").replaceAll('"', '""')}"`).join(",");
}

function normalizePhone(value) {
  return value.trim().replace(/[^\d+]/g, "");
}

function normalizeHashtag(value) {
  const cleaned = value.trim().replace(/^#+/, "").replace(/[,\s;]+/g, "");
  return cleaned ? `#${cleaned.toLowerCase()}` : "";
}

function splitHashtags(value) {
  return value.split(/[\s,;]+/).map(normalizeHashtag).filter(Boolean);
}

function textToList(value) {
  return String(value || "")
    .split(/[\n,;]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function listToText(value) {
  return (value || []).join("\n");
}

function uniqueCatalogOptions(values) {
  const rows = new Map();
  (values || []).forEach((value) => {
    const option = typeof value === "string" ? { key: value, value, label: value } : value;
    if (!option?.label) return;
    const key = String(option.value || option.label).toLocaleLowerCase("uz");
    if (!rows.has(key)) rows.set(key, option);
  });
  return [...rows.values()];
}

function catalogValue(item) {
  return item?.value || item?.label || item?.key || "";
}

function catalogMatches(item, value) {
  return [item?.value, item?.label, item?.key].some((candidate) => String(candidate || "") === String(value || ""));
}

function uniqueHashtags(tags) {
  const seen = new Set();
  return tags.filter((tag) => {
    const normalized = normalizeHashtag(tag);
    if (!normalized || seen.has(normalized)) return false;
    seen.add(normalized);
    return true;
  });
}

function telegramRef(source) {
  if (!source) return "";
  if (source.username) return `@${source.username}`;
  if (source.chat_id) return String(source.chat_id);
  return "";
}

function telegramTitle(source) {
  return source?.competitor_name || source?.title || telegramRef(source) || "Telegram source";
}

function telegramUrl(source) {
  if (source?.username) return `https://t.me/${source.username}`;
  return "";
}

function youtubeRef(source) {
  if (!source) return "";
  if (source.channel_handle) return source.channel_handle;
  if (source.channel_id) return source.channel_id;
  if (source.video_id) return source.video_id;
  return source.source_ref || source.query || "";
}

function youtubeTitle(source) {
  return source?.nickname || source?.title || source?.channel_title || source?.competitor_name || youtubeRef(source) || "YouTube source";
}

function youtubeUrl(source) {
  if (source?.video_id) return `https://www.youtube.com/watch?v=${source.video_id}`;
  if (source?.channel_handle) return `https://www.youtube.com/${source.channel_handle}`;
  if (source?.channel_id) return `https://www.youtube.com/channel/${source.channel_id}`;
  if (source?.source_ref?.startsWith("http")) return source.source_ref;
  if (source?.query) return `https://www.youtube.com/results?search_query=${encodeURIComponent(source.query)}`;
  return "";
}

function sourceDisplay(platform, source) {
  return platform === "telegram"
    ? { title: telegramTitle(source), ref: telegramRef(source), href: telegramUrl(source) }
    : { title: youtubeTitle(source), ref: youtubeRef(source), href: youtubeUrl(source) };
}

function sourceStatus(source) {
  return source?.active ? "Kuzatuvda" : "Pause";
}

function statusClass(source) {
  return source?.active ? "state ok" : "state neutral";
}

function profileSourceState(platform, source, telegramConnection, youtubeStatus) {
  if (!source?.active) return { label: "Pause", className: "state neutral" };
  if (platform === "telegram") {
    if (!source.connector_managed) return { label: "Yoqilgan", className: "state warn" };
    const capability = source.source_role === "discussion"
      ? telegramConnection?.capabilities?.discussion_monitoring
      : telegramConnection?.capabilities?.channel_monitoring;
    if (capability || source.telethon_access_status === "ready") {
      return { label: "Monitoring", className: "state ok" };
    }
    return {
      label: source.chat_id == null ? "Catalog" : "Access kutilmoqda",
      className: "state warn",
    };
  }
  if (platform === "youtube") {
    if (!youtubeStatus?.configured) return { label: "API kutilmoqda", className: "state warn" };
    if (source.source_kind === "channel" && (!source.channel_id || !source.uploads_playlist_id)) {
      return { label: "Kanal resolve kutilmoqda", className: "state warn" };
    }
    return { label: "Monitoring", className: "state ok" };
  }
  return { label: sourceStatus(source), className: statusClass(source) };
}

function countActive(items) {
  return items.filter((item) => item.active).length;
}

function sourceCategory(source) {
  return source.source_category || "unknown";
}

function isOwnedSource(source, brandId) {
  if (!brandId || source.brand_id !== brandId) return false;
  return sourceCategory(source) === "owned";
}

function metaSourceDisplay(platform, source) {
  if (platform === "instagram") {
    return {
      title: source.username ? `@${source.username}` : source.account_name || source.ig_user_id || "Instagram account",
      ref: source.ig_user_id,
      href: source.username ? `https://www.instagram.com/${source.username.replace(/^@/, "")}` : "",
    };
  }
  return {
    title: source.page_name || source.username || source.page_id || "Facebook Page",
    ref: source.page_id,
    href: source.username ? `https://www.facebook.com/${source.username}` : "",
  };
}

function ProfileSummary({ telegramSources, youtubeSources, instagramSources, facebookSources, selectedBrandName }) {
  const total = telegramSources.length + youtubeSources.length + instagramSources.length + facebookSources.length;
  const active = countActive(telegramSources) + countActive(youtubeSources) + countActive(instagramSources) + countActive(facebookSources);
  const paused = total - active;
  const cards = [
    { label: "Brand", value: selectedBrandName || "Tanlanmagan", icon: UserCog, tone: "profile" },
    { label: "Official source", value: total, icon: ShieldCheck, tone: "total" },
    { label: "Yoqilgan", value: active, icon: CheckCircle2, tone: "source" },
    { label: "Pause", value: paused, icon: Pause, tone: "risk" },
  ];

  return (
    <section className="profileSummaryGrid">
      {cards.map((item) => {
        const Icon = item.icon;
        return (
          <article className={`statCard ${item.tone}`} key={item.label}>
            <div>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
            <Icon size={22} />
          </article>
        );
      })}
    </section>
  );
}

function ActiveBrandSelector({ brands, selectedBrandId, onChange, onCreate }) {
  const { t } = useTranslation();
  const superAdmin = isSuperAdmin();
  const options = brands.map((brand) => ({
    value: brand.id,
    label: superAdmin && brand.owner_email
      ? `${brand.name} · ${brand.owner_email}`
      : brand.name,
    searchTerms: [brand.name, brand.owner_email, brand.owner_name].filter(Boolean),
  }));
  return (
    <section className="panel activeBrandToolbar">
      <div>
        <strong>{t("Faol brand")}</strong>
        <p>
          {superAdmin
            ? t("Super admin barcha brandlarni ko‘radi. Boshqa mijoz brandiga o‘tishda egasining login/paroli so‘raladi.")
            : t("Faqat o‘zingiz yaratgan brandlar ko‘rinadi. Dashboard va monitoring shu brand bo‘yicha.")}
        </p>
      </div>
      <SmartSelect
        value={selectedBrandId}
        options={options}
        onChange={onChange}
        emptyLabel={t("Brand mavjud emas")}
        ariaLabel={t("Faol brandni qidirish va tanlash")}
      />
      <button className="button secondary" type="button" onClick={onCreate}>
        <Plus size={16} />
        <span>{t("Yangi brand")}</span>
      </button>
    </section>
  );
}

function BrandUnlockModal({ brand, onCancel, onUnlocked }) {
  const { t } = useTranslation();
  const [email, setEmail] = useState(brand?.owner_email || "");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    if (!brand?.id) return;
    setBusy(true);
    setError("");
    try {
      await unlockBrand(brand.id, email.trim(), password);
      markBrandUnlocked(brand.id);
      onUnlocked?.(brand.id);
    } catch (err) {
      setError(err.message || t("Kirish rad etildi"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="brandUnlockOverlay" role="dialog" aria-modal="true" aria-labelledby="brand-unlock-title">
      <form className="brandUnlockCard panel" onSubmit={handleSubmit}>
        <h3 id="brand-unlock-title">{t("Brand himoyasi")}</h3>
        <p>
          <strong data-i18n-ignore="true">{brand?.name}</strong>{" "}
          {t("boshqa mijoz ish maydoni. Client xavfsizligi uchun brand egasining login va parolini kiriting.")}
        </p>
        {brand?.owner_email ? (
          <p className="muted small">
            {t("Ega:")} <span data-i18n-ignore="true">{brand.owner_name || brand.owner_email}</span>
          </p>
        ) : null}
        {error ? <div className="errorBanner">{error}</div> : null}
        <label className="field">
          <span>{t("Login (email)")}</span>
          <input
            className="input"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label className="field">
          <span>{t("Parol")}</span>
          <input
            className="input"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        <div className="brandUnlockActions">
          <button className="button" type="button" onClick={onCancel} disabled={busy}>
            {t("Bekor qilish")}
          </button>
          <button className="button primary" type="submit" disabled={busy || !password}>
            {busy ? t("Tekshirilmoqda...") : t("Brandni ochish")}
          </button>
        </div>
      </form>
    </div>
  );
}

function BrandIntelligencePanel({ brand, taxonomy, onSave, onCreate, saving }) {
  const { t, i18n } = useTranslation();
  const resolvedLanguage = i18n.resolvedLanguage || i18n.language || "uz";
  const defaultLanguage = brand?.language || (["uz", "ru", "en"].includes(resolvedLanguage) ? resolvedLanguage : "uz");
  const categories = taxonomy?.categories || [];
  const goals = taxonomy?.goals || [];
  // Analysis language for smart-fill / AI (100+). Separate from UI chrome (uz|ru|en only).
  const languageOptions = useMemo(() => {
    const fromTaxonomy = (taxonomy?.languages || taxonomy?.catalog?.languages || []).map((item) => ({
      value: item.value || item.key,
      label: item.label || item.value || item.key,
    }));
    if (fromTaxonomy.length) return uniqueCatalogOptions(fromTaxonomy);
    return [
      { value: "uz", label: t("O'zbek") },
      { value: "ru", label: t("Rus") },
      { value: "en", label: t("Ingliz") },
    ];
  }, [t, taxonomy?.catalog?.languages, taxonomy?.languages]);
  const [form, setForm] = useState(() => buildBrandForm(brand, defaultLanguage));
  const [selectionTouched, setSelectionTouched] = useState(false);
  const [suggestion, setSuggestion] = useState({ status: "idle", message: "", model: "" });
  const suggestionRequestRef = useRef(0);
  const currentSignatureRef = useRef("");
  const analysisLanguage = form.language || defaultLanguage;

  useEffect(() => {
    setForm(buildBrandForm(brand, brand?.language || defaultLanguage));
    setSelectionTouched(false);
    setSuggestion({ status: "idle", message: "", model: "" });
  }, [brand?.id]);

  const selectedCategory = categories.find((item) => catalogMatches(item, form.primary_category));
  const primaryOptions = form.primary_category && !selectedCategory
    ? [{ value: form.primary_category, label: form.primary_category }, ...categories]
    : categories;
  const allChildOptions = useMemo(() => uniqueCatalogOptions(categories.flatMap((category) => category.children || [])), [categories]);
  const catalogActivities = taxonomy?.catalog?.activities || [];
  const catalogModels = taxonomy?.catalog?.business_models || [];
  const catalogAudience = taxonomy?.catalog?.audience_segments || [];
  const allActivityOptions = useMemo(() => {
    const nested = categories.flatMap((category) => category.activities || [])
      .concat(categories.flatMap((category) => (category.children || []).flatMap((child) => child.activities || [])));
    return uniqueCatalogOptions([...(catalogActivities || []), ...nested]);
  }, [catalogActivities, categories]);
  const allBusinessModelOptions = useMemo(() => {
    const nested = allActivityOptions.flatMap((activity) => activity.business_models || []);
    return uniqueCatalogOptions([...(catalogModels || []), ...nested]);
  }, [allActivityOptions, catalogModels]);
  const allAudienceOptions = useMemo(
    () => uniqueCatalogOptions([
      ...(catalogAudience || []),
      ...Object.values(taxonomy?.audience_groups || {}).flat(),
    ]),
    [catalogAudience, taxonomy?.audience_groups],
  );
  const childOptions = uniqueCatalogOptions(selectedCategory?.children || []);
  const selectedChild = allChildOptions.find((item) => catalogMatches(item, form.sub_category));
  // Activities live on category (lean taxonomy v3) with legacy child fallback.
  const activityOptions = selectedCategory?.activities || selectedChild?.activities || [];
  const selectedActivity = allActivityOptions.find((item) => catalogMatches(item, form.activity))
    || activityOptions.find((item) => catalogMatches(item, form.activity));
  const businessModelOptions = selectedActivity?.business_models || [];
  const selectedBusinessModel = allBusinessModelOptions.find((item) => catalogMatches(item, form.business_model))
    || businessModelOptions.find((item) => catalogMatches(item, form.business_model));
  const audienceOptions = uniqueCatalogOptions((selectedBusinessModel?.audience_groups || [])
    .flatMap((groupKey) => taxonomy?.audience_groups?.[groupKey] || []));
  const selectedGoalKeys = new Set(form.monitoring_goals);
  const readinessItems = [
    ["Brand nomi", form.name.trim()],
    ["Faoliyat tavsifi", form.description.trim()],
    ["Yo'nalish", form.primary_category],
    ["Faoliyat modeli", form.activity && form.business_model],
    ["Alias yoki keyword", textToList(form.aliases).length || textToList(form.keywords).length],
    ["Mahsulot/xizmat", textToList(form.products).length],
    ["Auditoriya", form.audience.trim()],
    ["Bozor", form.region.trim()],
    ["Monitoring maqsadi", form.monitoring_goals.length],
  ];
  const completedReadiness = readinessItems.filter(([, value]) => Boolean(value)).length;
  const readiness = Math.round((completedReadiness / readinessItems.length) * 100);
  const missingReadiness = readinessItems.filter(([, value]) => !value).map(([label]) => label);
  const suggestionReady = Boolean(
    form.name.trim()
    && form.primary_category
    && form.sub_category
    && form.activity
    && form.business_model
    && form.audience_segment
  );
  const suggestionSignature = [
    form.name.trim(),
    form.website.trim(),
    form.primary_category,
    form.sub_category,
    form.activity,
    form.business_model,
    form.audience_segment,
    form.region.trim(),
    analysisLanguage,
  ].join("|");
  currentSignatureRef.current = suggestionSignature;

  useEffect(() => {
    if (!selectionTouched || !suggestionReady) return undefined;
    // Short debounce: wait until chained selects settle, then fill immediately (fresh = no heavy existing_values).
    const timer = window.setTimeout(() => {
      generateSuggestions(suggestionSignature, { fresh: true });
    }, 160);
    return () => window.clearTimeout(timer);
  }, [selectionTouched, suggestionReady, suggestionSignature]);

  async function generateSuggestions(requestSignature = suggestionSignature, options = {}) {
    const fresh = options.fresh !== false;
    if (!suggestionReady) {
      setSuggestion({
        status: "error",
        message: t("Avval yo'nalishdan auditoriya segmentigacha bo'lgan bog'langan tanlovlarni to'ldiring."),
        model: "",
      });
      return;
    }
    if (!form.name.trim()) {
      setSuggestion({ status: "error", message: t("Aqlli to'ldirish uchun brand nomini kiriting."), model: "" });
      return;
    }
    const requestId = suggestionRequestRef.current + 1;
    suggestionRequestRef.current = requestId;
    setSuggestion({ status: "loading", message: t("Gemini Pro profil maydonlarini tayyorlamoqda..."), model: "" });
    try {
      // Fresh re-fill after taxonomy changes: skip large existing_values so Gemini responds faster.
      const existing_values = fresh
        ? {}
        : {
            description: form.description.trim(),
            audience: form.audience.trim(),
            aliases: textToList(form.aliases),
            keywords: textToList(form.keywords),
            products: textToList(form.products),
            competitors: textToList(form.competitors),
            risk_keywords: textToList(form.risk_keywords),
            positive_keywords: textToList(form.positive_keywords),
            ignore_terms: textToList(form.ignore_terms),
            monitor_notes: form.monitor_notes.trim(),
          };
      const response = await endpoints.brandProfileSuggestions({
        name: form.name.trim(),
        website: form.website.trim() || null,
        language: analysisLanguage,
        category_path: [form.primary_category, form.sub_category, form.activity, form.business_model, form.audience_segment].filter(Boolean),
        business_model: form.business_model,
        audience_segment: form.audience_segment || null,
        region: form.region.trim() || null,
        existing_values,
      });
      if (requestId !== suggestionRequestRef.current || requestSignature !== currentSignatureRef.current) return;
      setForm((current) => ({
        ...current,
        description: response.description || "",
        audience: response.audience || "",
        aliases: listToText(response.aliases || []),
        keywords: listToText(response.keywords || []),
        products: listToText(response.products || []),
        competitors: listToText(response.competitors || []),
        risk_keywords: listToText(response.risk_keywords || []),
        positive_keywords: listToText(response.positive_keywords || []),
        ignore_terms: listToText(response.ignore_terms || []),
        monitor_notes: response.monitor_notes || "",
      }));
      setSelectionTouched(false);
      setSuggestion({
        status: "success",
        message: t("Maydonlar aqlli tarzda to'ldirildi. Har bir qiymatni qo'lda tahrirlashingiz mumkin."),
        model: response.model_name || "Gemini Pro",
      });
    } catch (error) {
      if (requestId !== suggestionRequestRef.current) return;
      setSuggestion({
        status: "error",
        message: error?.message || t("Aqlli to'ldirish ishlamadi. Qayta urinib ko'ring."),
        model: "",
      });
    }
  }

  function buildPayload() {
    const categoryPath = [form.primary_category, form.sub_category, form.activity, form.business_model, form.audience_segment].filter(Boolean);
    return {
      name: form.name.trim(),
      description: form.description.trim() || null,
      industry: form.activity || form.sub_category || form.primary_category || null,
      primary_category: form.primary_category || null,
      category_path: categoryPath,
      website: form.website.trim() || null,
      language: analysisLanguage,
      aliases: textToList(form.aliases),
      keywords: textToList(form.keywords),
      products: textToList(form.products),
      competitors: textToList(form.competitors),
      ignore_terms: textToList(form.ignore_terms),
      audience: form.audience.trim() || null,
      region: form.region.trim() || null,
      monitoring_goals: form.monitoring_goals,
      risk_keywords: textToList(form.risk_keywords),
      positive_keywords: textToList(form.positive_keywords),
      monitor_notes: form.monitor_notes.trim() || null,
      profile_config: {
        ...(brand?.profile_config || {}),
        onboarding_version: 2,
        activity: form.activity || null,
        business_model: form.business_model || null,
        audience_segment: form.audience_segment || null,
        own_profile_priority: form.own_profile_priority,
        competitor_priority: form.competitor_priority,
        global_watch_priority: form.global_watch_priority,
      },
    };
  }

  function handleCategory(value) {
    const meta = categories.find((item) => catalogMatches(item, value));
    setSelectionTouched(true);
    setForm((current) => ({
      ...current,
      primary_category: catalogValue(meta) || value,
      sub_category: "",
      activity: "",
      business_model: "",
      audience_segment: "",
    }));
  }

  function handleDependentSelection(field, value, resets) {
    setSelectionTouched(true);
    setSuggestion({ status: "idle", message: "", model: "" });
    setForm((current) => ({
      ...current,
      [field]: value,
      ...Object.fromEntries(resets.map((key) => [key, ""])),
    }));
  }

  function toggleGoal(key) {
    setForm((current) => {
      const exists = current.monitoring_goals.includes(key);
      return {
        ...current,
        monitoring_goals: exists
          ? current.monitoring_goals.filter((item) => item !== key)
          : [...current.monitoring_goals, key],
      };
    });
  }

  function handleSubmit(event) {
    event.preventDefault();
    if (!form.name.trim()) return;
    if (brand?.id) {
      onSave(brand.id, buildPayload());
    } else {
      onCreate(buildPayload());
    }
  }

  return (
    <section className="panel brandBrainPanel">
      <div className="sectionHeader compact">
        <div>
          <span className="eyebrow">Brand intelligence</span>
          <h2><Brain size={18} /> Brandni loyihaga tanitish</h2>
          <p>Bu ma'lumotlar matching, AI relevance gate va deep analysis uchun asos bo'ladi.</p>
        </div>
        <div className="profileReadiness" title={missingReadiness.length ? `Yetishmaydi: ${missingReadiness.join(", ")}` : "Profil tayyor"}>
          <span>Profil tayyorligi</span>
          <strong>{readiness}%</strong>
          <i><b style={{ width: `${readiness}%` }} /></i>
        </div>
      </div>

      <form className="brandBrainForm" onSubmit={handleSubmit}>
          <div className="brandBrainGrid">
            <label className="field">
              <span>Brand nomi</span>
              <input className="input" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required />
              <p className="fieldHint">Monitoringda ishlatiladigan rasmiy va aniq brand nomini kiriting.</p>
            </label>
            <label className="field">
              <span>Website <small className="optionalMark">ixtiyoriy</small></span>
              <input className="input" value={form.website} onChange={(event) => setForm({ ...form, website: event.target.value })} />
              <p className="fieldHint">Rasmiy sayt mavjud bo'lsa kiriting; bu maydon majburiy emas.</p>
            </label>
            <label className="field">
              <span>Asosiy yo'nalish</span>
              <SmartSelect
                value={form.primary_category}
                options={primaryOptions}
                onChange={handleCategory}
                ariaLabel="Asosiy yo'nalishni qidirish va tanlash"
              />
              <p className="fieldHint">Brand faoliyatini eng keng ifodalovchi sohani qidirib tanlang.</p>
            </label>
            <label className="field">
              <span>Ichki yo'nalish</span>
              <SmartSelect
                value={form.sub_category}
                options={childOptions}
                fallbackOptions={allChildOptions}
                onChange={(value) => handleDependentSelection("sub_category", value, ["activity", "business_model", "audience_segment"])}
                disabled={!form.primary_category}
                ariaLabel="Ichki yo'nalishni qidirish va tanlash"
              />
              <p className="fieldHint">Avval asosiy sohaga mos tavsiyalar chiqadi. Keraklisi ko'rinmasa, qidiruvga yozib butun katalogdan tanlang.</p>
            </label>
            <label className="field">
              <span>Faoliyat turi</span>
              <SmartSelect
                value={form.activity}
                options={activityOptions}
                fallbackOptions={allActivityOptions}
                onChange={(value) => handleDependentSelection("activity", value, ["business_model", "audience_segment"])}
                disabled={!form.sub_category}
                ariaLabel="Faoliyat turini qidirish va tanlash"
              />
              <p className="fieldHint">Ichki yo'nalishga mos faoliyatlar tavsiya qilinadi; boshqa variantni qidirib butun katalogdan olish mumkin.</p>
            </label>
            <label className="field">
              <span>Biznes modeli</span>
              <SmartSelect
                value={form.business_model}
                options={businessModelOptions}
                fallbackOptions={allBusinessModelOptions}
                onChange={(value) => handleDependentSelection("business_model", value, ["audience_segment"])}
                disabled={!form.activity}
                ariaLabel="Biznes modelini qidirish va tanlash"
              />
              <p className="fieldHint">Faoliyatga mos biznes modellari tavsiya qilinadi; topilmasa qidiruv barcha modellarni ko'rsatadi.</p>
            </label>
            <label className="field">
              <span>Auditoriya segmenti</span>
              <SmartSelect
                value={form.audience_segment}
                options={audienceOptions}
                fallbackOptions={allAudienceOptions}
                onChange={(value) => handleDependentSelection("audience_segment", value, [])}
                disabled={!form.business_model}
                ariaLabel="Auditoriya segmentini qidirish va tanlash"
              />
              <p className="fieldHint">Biznes modeliga mos segmentlar tavsiya qilinadi; kerakli auditoriyani butun katalogdan ham qidirish mumkin.</p>
            </label>
            <label className="field">
              <span>Tahlil tili</span>
              <SmartSelect
                value={form.language || analysisLanguage}
                options={languageOptions}
                onChange={(value) => {
                  setSelectionTouched(true);
                  setForm((current) => ({ ...current, language: value }));
                }}
                ariaLabel="Tahlil tilini qidirish va tanlash"
              />
              <p className="fieldHint">{t("Gemini aqlli to‘ldirish va AI xulosalari shu tahlil tilida yaratiladi (100+ til). Interfeys tili alohida: o‘zbek, rus, ingliz.")}</p>
            </label>
            <label className="field spanTwo">
              <span>Brand nima qiladi</span>
              <textarea className="input textarea" rows="3" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
              <p className="fieldHint">Mahsulot, xizmat va mijozga beriladigan asosiy qiymatni qisqa bayon qiling.</p>
            </label>
            <label className="field spanTwo">
              <span>Auditoriya</span>
              <textarea className="input textarea" rows="3" value={form.audience} onChange={(event) => setForm({ ...form, audience: event.target.value })} />
              <p className="fieldHint">Xaridor, foydalanuvchi, qaror qabul qiluvchi va ta'sir qiluvchi guruhlarni tavsiflang.</p>
            </label>
            <label className="field">
              <span>Hudud / bozor</span>
              <input className="input" value={form.region} onChange={(event) => setForm({ ...form, region: event.target.value })} />
              <p className="fieldHint">Brand ishlaydigan davlat, shahar yoki bozorlar doirasini kiriting.</p>
            </label>
          </div>

          <div className={`aiSuggestionBar ${suggestion.status}`}>
            <div>
              <Sparkles size={18} />
              <span>
                <strong>Gemini Pro aqlli profil</strong>
                <small>{suggestion.message || "Bog'langan tanlovlar yakunlangach profil maydonlari avtomatik tayyorlanadi."}</small>
              </span>
            </div>
            <button
              className="miniButton"
              type="button"
              disabled={!suggestionReady || suggestion.status === "loading"}
              onClick={() => generateSuggestions(suggestionSignature, { fresh: true })}
            >
              <RefreshCw size={15} />
              <span>
                {suggestion.status === "loading"
                  ? t("Tahlil qilmoqda...")
                  : suggestion.status === "success"
                    ? t("Qayta to'ldirish")
                    : t("Aqlli to'ldirish")}
              </span>
            </button>
            {suggestion.model && <em>{suggestion.model}</em>}
          </div>

          <div className="priorityPicker">
            <div>
              <strong><Target size={15} /> Monitoring ustuvorligi</strong>
              <span>Source va tahlil oqimida qaysi signal birinchi o'rinda turishini belgilang.</span>
            </div>
            <div className="priorityGrid">
              <label className={form.own_profile_priority ? "priorityOption active" : "priorityOption"}>
                <input type="checkbox" checked={form.own_profile_priority} onChange={(event) => setForm({ ...form, own_profile_priority: event.target.checked })} />
                <span><strong>O'z profillari</strong><small>Official post, comment va discussionlar</small></span>
              </label>
              <label className={form.competitor_priority ? "priorityOption active" : "priorityOption"}>
                <input type="checkbox" checked={form.competitor_priority} onChange={(event) => setForm({ ...form, competitor_priority: event.target.checked })} />
                <span><strong>Raqobatchilar</strong><small>Profil, kanal va kampaniya kuzatuvi</small></span>
              </label>
              <label className={form.global_watch_priority ? "priorityOption active" : "priorityOption"}>
                <input type="checkbox" checked={form.global_watch_priority} onChange={(event) => setForm({ ...form, global_watch_priority: event.target.checked })} />
                <span><strong>Global mention</strong><small>Media, community va umumiy brand signali</small></span>
              </label>
            </div>
          </div>

          <div className="brandBrainLists">
            <label className="field">
              <span><Tags size={14} /> Alias va yozilish variantlari</span>
              <textarea className="input textarea" rows="5" value={form.aliases} onChange={(event) => setForm({ ...form, aliases: event.target.value })} />
              <p className="fieldHint">Brand nomining lotin, kirill, qisqartma va keng tarqalgan xato yozilishlarini har qatorda bittadan kiriting.</p>
            </label>
            <label className="field">
              <span><Hash size={14} /> Keyword va kampaniya so'zlari</span>
              <textarea className="input textarea" rows="5" value={form.keywords} onChange={(event) => setForm({ ...form, keywords: event.target.value })} />
              <p className="fieldHint">Brend, kampaniya, xarid niyati va mavzuga bog'liq kalit iboralarni kiriting.</p>
            </label>
            <label className="field">
              <span><Target size={14} /> Product/xizmatlar</span>
              <textarea className="input textarea" rows="5" value={form.products} onChange={(event) => setForm({ ...form, products: event.target.value })} />
              <p className="fieldHint">Monitoringda alohida aniqlanishi kerak bo'lgan mahsulot va xizmatlarni yozing.</p>
            </label>
            <label className="field">
              <span><Globe2 size={14} /> Raqobatchilar yoki kuzatiladigan profillar</span>
              <textarea className="input textarea" rows="5" value={form.competitors} onChange={(event) => setForm({ ...form, competitors: event.target.value })} />
              <p className="fieldHint">Taqqoslash uchun raqobatchi brandlar yoki kuzatiladigan ochiq profil nomlarini kiriting.</p>
            </label>
            <label className="field">
              <span>Risk so'zlari</span>
              <textarea className="input textarea" rows="5" value={form.risk_keywords} onChange={(event) => setForm({ ...form, risk_keywords: event.target.value })} />
              <p className="fieldHint">Shikoyat, nosozlik, firibgarlik yoki reputatsion inqirozni bildiruvchi so'zlarni kiriting.</p>
            </label>
            <label className="field">
              <span>Ijobiy signal so'zlari</span>
              <textarea className="input textarea" rows="5" value={form.positive_keywords} onChange={(event) => setForm({ ...form, positive_keywords: event.target.value })} />
              <p className="fieldHint">Mamnunlik, tavsiya, sifat va muvaffaqiyatni bildiruvchi signallarni yozing.</p>
            </label>
            <label className="field">
              <span>Tahlildan chiqariladigan so'zlar</span>
              <textarea className="input textarea" rows="5" value={form.ignore_terms} onChange={(event) => setForm({ ...form, ignore_terms: event.target.value })} />
              <p className="fieldHint">Brandga aloqasiz omonim, spam va tahlil natijasini buzadigan shovqin so'zlarini kiriting.</p>
            </label>
          </div>

          <div className="goalPicker">
            <div>
              <strong><ListChecks size={15} /> Monitoring maqsadlari</strong>
              <span>Tanlangan maqsadlar platformalardagi default source mantiqiga asos bo'ladi.</span>
            </div>
            <div className="goalGrid">
              {goals.map((goal) => (
                <button
                  className={selectedGoalKeys.has(goal.key) ? "goalChip active" : "goalChip"}
                  type="button"
                  key={goal.key}
                  onClick={() => toggleGoal(goal.key)}
                >
                  {goal.label}
                </button>
              ))}
            </div>
          </div>

          <label className="field full">
            <span>AI uchun qo'shimcha qoida</span>
            <textarea className="input textarea" rows="3" value={form.monitor_notes} onChange={(event) => setForm({ ...form, monitor_notes: event.target.value })} />
            <p className="fieldHint">AI qaysi kontekst, istisno yoki biznes qoidasiga alohida e'tibor berishini yozing.</p>
          </label>

          <div className="buttonRow">
            <button className="button primary" type="submit" disabled={saving || !form.name.trim()}>
              <Save size={17} />
              <span>{saving ? "Saqlanmoqda..." : brand?.id ? "Brand intelligence saqlash" : "Brand yaratish"}</span>
            </button>
          </div>
        </form>
    </section>
  );
}

function buildBrandForm(brand, preferredLanguage = "uz") {
  const config = brand?.profile_config || {};
  // Analysis language may be any supported ISO code (100+); default to UI preference.
  const language = brand?.language || preferredLanguage || "uz";
  return {
    name: brand?.name || "",
    description: brand?.description || "",
    website: brand?.website || "",
    primary_category: brand?.primary_category || brand?.industry || "",
    sub_category: brand?.category_path?.[1] || "",
    activity: brand?.category_path?.[2] || config.activity || "",
    business_model: brand?.category_path?.[3] || config.business_model || "",
    audience_segment: brand?.category_path?.[4] || config.audience_segment || "",
    language,
    aliases: listToText(brand?.aliases),
    keywords: listToText(brand?.keywords),
    products: listToText(brand?.products),
    competitors: listToText(brand?.competitors),
    ignore_terms: listToText(brand?.ignore_terms),
    audience: brand?.audience || "",
    region: brand?.region || "",
    monitoring_goals: brand?.monitoring_goals || ["own_profile", "competitor_watch"],
    risk_keywords: listToText(brand?.risk_keywords),
    positive_keywords: listToText(brand?.positive_keywords),
    monitor_notes: brand?.monitor_notes || "",
    own_profile_priority: config.own_profile_priority ?? true,
    competitor_priority: config.competitor_priority ?? true,
    global_watch_priority: config.global_watch_priority ?? false,
  };
}

function AdminIdentityPanel({ session, onSave, onLogout }) {
  const [form, setForm] = useState({
    display_name: session?.display_name || session?.username || "",
    username: session?.username || "",
    phone: session?.phone || "",
  });

  useEffect(() => {
    setForm({
      display_name: session?.display_name || session?.username || "",
      username: session?.username || "",
      phone: session?.phone || "",
    });
  }, [session]);

  function handleSubmit(event) {
    event.preventDefault();
    onSave({
      ...session,
      ...form,
      phone: normalizePhone(form.phone),
      updated_at: new Date().toISOString(),
    });
  }

  return (
    <article className="panel identityPanel">
      <div className="sectionHeader compact">
        <div>
          <h2><UserCog size={18} /> Admin akkaunt</h2>
          <p>Bu bo'lim tizim operatori kimligini va Telegram sessiya egasini aniq ko'rsatadi.</p>
        </div>
        <button className="miniButton" type="button" onClick={onLogout}>
          <LogOut size={15} />
          <span>Chiqish</span>
        </button>
      </div>

      <form className="identityForm" onSubmit={handleSubmit}>
        <label className="field">
          <span>Admin nomi</span>
          <input
            className="input"
            value={form.display_name}
            onChange={(event) => setForm((current) => ({ ...current, display_name: event.target.value }))}
          />
          <p className="fieldHint">Dashboardda ko'rinadigan mas'ul administratorning ism-familiyasini kiriting.</p>
        </label>
        <label className="field">
          <span>Login</span>
          <input
            className="input"
            value={form.username}
            readOnly
            aria-readonly="true"
          />
          <p className="fieldHint">Bu Login sahifasida tizimga kirishda ishlatilgan username. Xavfsizlik sababli bu yerda o'zgartirilmaydi.</p>
        </label>
        <label className="field">
          <span>Telegram telefon</span>
          <input
            className="input"
            value={form.phone}
            onChange={(event) => setForm((current) => ({ ...current, phone: event.target.value }))}
            inputMode="tel"
          />
          <p className="fieldHint">Telethon sessiyasi ochilgan telefon raqamini xalqaro formatda kiriting, masalan: +998 XX XXX XX XX.</p>
        </label>
        <div className="identityNote">
          <CalendarClock size={16} />
          <span>Telegram monitoring access'i bot token va Telethon session orqali ishlaydi; bu telefon profil egasini aniqlash uchun.</span>
        </div>
        <button className="button secondary fullButton" type="submit">
          <Save size={17} />
          <span>Profilni saqlash</span>
        </button>
      </form>
    </article>
  );
}

function PlatformRegistry({
  platform,
  telegramSources,
  telegramConnection,
  youtubeSources,
  youtubeStatus,
  instagramSources,
  facebookSources,
  onOpenCreate,
  onOpenEdit,
  onOpenReplace,
  onToggle,
  onRefresh,
  onDelete,
}) {
  const isTelegram = platform === "telegram";
  const isYoutube = platform === "youtube";
  const isMeta = platform === "instagram" || platform === "facebook";
  const sources = isTelegram
    ? telegramSources
    : isYoutube
    ? youtubeSources
    : platform === "instagram"
    ? instagramSources
    : facebookSources;
  const meta = platformTabs.find((item) => item.key === platform) || platformTabs[0];
  const Icon = meta.icon;

  if (isMeta) {
    return (
      <article className={`panel profileRegistryPanel ${meta.tone}`}>
        <div className="sectionHeader compact">
          <div>
            <h2><Icon size={18} /> {meta.label} official source</h2>
            <p>{meta.description}</p>
          </div>
          <a className="button primary linkButton" href={`/${platform}-monitoring`}>
            <ExternalLink size={17} />
            <span>Ulash sahifasi</span>
          </a>
        </div>

        <div className="profileSourceList">
          {sources.length ? (
            sources.map((source) => {
              const display = metaSourceDisplay(platform, source);
              return (
                <article className="profileSourceCard" key={`${platform}-${source.id}`}>
                  <div className="profileSourceMain">
                    <div className={`profileSourceIcon ${platform}`}>
                      <Icon size={19} />
                    </div>
                    <div>
                      <strong>{display.title}</strong>
                      <span>{display.ref || "Platform ID hali aniqlanmagan"}</span>
                    </div>
                    <em className={statusClass(source)}>{sourceStatus(source)}</em>
                  </div>

                  <div className="sourceSignals profileChips">
                    <span>{source.monitoring_mode === "all_messages" ? "all messages" : "brand matches"}</span>
                    <span>{source.collect_comments ? "comment" : "comment off"}</span>
                    <span>{source.collect_mentions ? "mention" : "mention off"}</span>
                    <span className={source.token_status === "active" ? "accent" : "blue"}>{source.token_status}</span>
                  </div>

                  {source.notes && <p className="sourceRowNote">{source.notes}</p>}

                  <div className="profileSourceActions">
                    <a className="miniButton linkButton" href={`/${platform}-monitoring`}>
                      <ExternalLink size={15} />
                      <span>Boshqarish</span>
                    </a>
                    {display.href && (
                      <a className="miniButton linkButton" href={display.href} target="_blank" rel="noreferrer">
                        <ExternalLink size={15} />
                        <span>Ochish</span>
                      </a>
                    )}
                    <button className="miniButton danger" type="button" onClick={() => onDelete(platform, source)}>
                      <Trash2 size={15} />
                      <span>O'chirish</span>
                    </button>
                  </div>
                </article>
              );
            })
          ) : (
            <div className="empty profileEmpty">
              <strong>{meta.label} source yo'q</strong>
              <span>Token va ruxsatlarni shu platformaning monitoring sahifasida ulang.</span>
            </div>
          )}
        </div>
      </article>
    );
  }

  return (
    <article className={`panel profileRegistryPanel ${meta.tone}`}>
      <div className="sectionHeader compact">
        <div>
          <h2><Icon size={18} /> {meta.label} official source</h2>
          <p>{meta.description}</p>
        </div>
        <button className="button primary" type="button" onClick={() => onOpenCreate(platform)}>
          <Plus size={17} />
          <span>Qo'shish</span>
        </button>
      </div>

      <div className="profileSourceList">
        {sources.length ? (
          sources.map((source) => (
            <ProfileSourceCard
              key={`${platform}-${source.id}`}
              platform={platform}
              source={source}
              telegramConnection={telegramConnection}
              youtubeStatus={youtubeStatus}
              onEdit={() => onOpenEdit(platform, source)}
              onReplace={() => onOpenReplace(platform, source)}
              onToggle={() => onToggle(platform, source)}
              onRefresh={() => onRefresh(platform, source)}
              onDelete={() => onDelete(platform, source)}
            />
          ))
        ) : (
          <div className="empty profileEmpty">
            <strong>Official source yo'q</strong>
            <span>Brandning rasmiy kanal/blog linkini qo'shing.</span>
          </div>
        )}
      </div>
    </article>
  );
}

function ProfileSourceCard({
  platform,
  source,
  telegramConnection,
  youtubeStatus,
  onEdit,
  onReplace,
  onToggle,
  onRefresh,
  onDelete,
}) {
  const display = sourceDisplay(platform, source);
  const monitoringState = profileSourceState(platform, source, telegramConnection, youtubeStatus);
  const isTelegram = platform === "telegram";
  const Icon = isTelegram ? TelegramIcon : YouTubeIcon;
  const chips = isTelegram
    ? [
        source.source_kind || "unknown",
        source.monitoring_mode || "all_messages",
        source.collect_posts ? "post" : "",
        source.collect_comments ? "comment" : "",
        source.linked_discussion_chat_id ? "linked chat" : "",
      ].filter(Boolean)
    : [
        source.source_kind || "unknown",
        source.monitoring_mode || "brand_matches_only",
        source.collect_videos ? "video" : "",
        source.collect_comments ? "comment" : "",
        source.collect_transcripts ? "transcript" : "",
      ].filter(Boolean);
  const href = display.href;

  return (
    <article className="profileSourceCard">
      <div className="profileSourceMain">
        <div className={`profileSourceIcon ${platform}`}>
          <Icon size={19} />
        </div>
        <div>
          <strong>{display.title}</strong>
          <span>{display.ref || "Platform ID hali resolve qilinmagan"}</span>
        </div>
        <em className={monitoringState.className}>{monitoringState.label}</em>
      </div>

      <div className="sourceSignals profileChips">
        {chips.map((chip) => <span key={chip}>{chip}</span>)}
        {platform === "youtube" && !!source.hashtags?.length && <span className="blue">{source.hashtags.length} hashtag</span>}
      </div>

      {source.notes && <p className="sourceRowNote">{source.notes}</p>}

      <div className="profileSourceActions">
        <button className="miniButton" type="button" onClick={onEdit}>
          <Save size={15} />
          <span>Tahrirlash</span>
        </button>
        <button className="miniButton" type="button" onClick={onReplace}>
          <Link2 size={15} />
          <span>Almashtirish</span>
        </button>
        <button className="miniButton" type="button" onClick={onRefresh}>
          <RefreshCw size={15} />
          <span>{isTelegram ? "Refresh" : "Sync"}</span>
        </button>
        <button className="miniButton" type="button" onClick={onToggle}>
          {source.active ? <Pause size={15} /> : <Play size={15} />}
          <span>{source.active ? "Pause" : "Davom"}</span>
        </button>
        <button className="miniButton danger" type="button" onClick={onDelete}>
          <Trash2 size={15} />
          <span>O'chirish</span>
        </button>
        {href && (
          <a className="miniButton linkButton" href={href} target="_blank" rel="noreferrer">
            <ExternalLink size={15} />
            <span>Ochish</span>
          </a>
        )}
      </div>
    </article>
  );
}

function SourceEditorModal({
  mode,
  platform,
  source,
  selectedBrandId,
  selectedBrandName,
  telegramInitialConnection,
  youtubeStatus,
  onClose,
  onSave,
  saving,
  result,
}) {
  const isTelegram = platform === "telegram";
  const isReplace = mode === "replace";
  const isEdit = mode === "edit";
  const display = sourceDisplay(platform, source);
  const initialYoutubeFields = isEdit
    ? officialChannelFieldsFromSource(source)
    : { channelUrl: "", handle: "", channelId: "" };
  const [form, setForm] = useState(() => ({
    ref: isTelegram ? telegramRef(source) : "",
    youtubeChannelUrl: initialYoutubeFields.channelUrl,
    youtubeHandle: initialYoutubeFields.handle,
    youtubeChannelId: initialYoutubeFields.channelId,
    displayName: isTelegram ? source?.competitor_name || source?.title || "" : source?.nickname || source?.channel_title || "",
    notes: source?.notes || "",
    monitorFrom: dateInputValue(source?.monitor_from),
    active: source?.active ?? true,
    collectPosts: source?.collect_posts ?? true,
    collectComments: source?.collect_comments ?? true,
    collectVideos: source?.collect_videos ?? true,
    collectTranscripts: source?.collect_transcripts ?? false,
    hashtags: uniqueHashtags(source?.hashtags || []),
    hashtagInput: "",
  }));
  const [formError, setFormError] = useState("");

  const title = isEdit ? "Official source tahrirlash" : isReplace ? "Official source almashtirish" : "Official source qo'shish";
  const parsedYoutubeRef = officialChannelRef({
    channelUrl: form.youtubeChannelUrl,
    handle: form.youtubeHandle,
    channelId: form.youtubeChannelId,
  });
  const refChanged = isTelegram
    ? Boolean(form.ref.trim() && form.ref.trim() !== display.ref)
    : Boolean(
      !parsedYoutubeRef.error
      && parsedYoutubeRef.canonicalRef !== canonicalOfficialChannelSourceRef(source),
    );

  function updateYoutubeField(field, value) {
    setFormError("");
    setForm((current) => ({
      ...current,
      youtubeChannelUrl: field === "url" ? value : "",
      youtubeHandle: field === "handle" ? value : "",
      youtubeChannelId: field === "id" ? value : "",
    }));
  }

  function addHashtags() {
    const next = uniqueHashtags([...form.hashtags, ...splitHashtags(form.hashtagInput)]);
    setForm((current) => ({ ...current, hashtags: next, hashtagInput: "" }));
  }

  function handleHashtagKeyDown(event) {
    if (event.key === "Enter" || event.key === "," || event.key === "Tab") {
      if (!form.hashtagInput.trim()) return;
      event.preventDefault();
      addHashtags();
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    let ref = form.ref.trim();
    if (isTelegram) {
      if (!ref) return;
    } else {
      if (parsedYoutubeRef.error) {
        setFormError(parsedYoutubeRef.error);
        return;
      }
      ref = parsedYoutubeRef.ref;
    }
    onSave({
      mode,
      platform,
      source,
      selectedBrandId,
      ref,
      refChanged,
      displayName: form.displayName.trim(),
      notes: form.notes.trim(),
      monitorFrom: form.monitorFrom,
      active: form.active,
      collectPosts: form.collectPosts,
      collectComments: form.collectComments,
      collectVideos: form.collectVideos,
      collectTranscripts: isTelegram ? form.collectTranscripts : false,
      hashtags: uniqueHashtags([...form.hashtags, ...splitHashtags(form.hashtagInput)]),
    });
  }

  if (isTelegram && (mode === "create" || source?.connector_managed)) {
    return (
      <div className="modalOverlay" role="presentation" onMouseDown={onClose}>
        <section className="modalPanel" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
          <div className="modalHeader">
            <div>
              <h2>Telegram ulanishini qo'shish</h2>
              <p>Bot, rasmiy kanal va discussion groupni brandga mustaqil ulang.</p>
            </div>
            <button className="iconButton" type="button" aria-label="Yopish" onClick={onClose}>
              <X size={18} />
            </button>
          </div>
          <div className="profileModalContent">
            <TelegramConnectionForm
              selectedBrandId={selectedBrandId}
              selectedBrandName={selectedBrandName}
              initialConnection={telegramInitialConnection}
              result={result}
              saving={saving}
              submitLabel="Telegram ulanishini qo'shish"
              onSubmit={(telegramSetup) => onSave({
                mode,
                platform,
                source,
                selectedBrandId,
                telegramSetup,
              })}
            />
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="modalOverlay" role="presentation" onMouseDown={onClose}>
      <section className="modalPanel profileModal" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
        <div className="modalHeader">
          <div>
            <h2>{title}</h2>
            <p>{isReplace ? "Yangi link resolve qilinadi, eski source pause holatida qoladi." : "Brandning rasmiy source registrini boshqarish."}</p>
          </div>
          <button className="iconButton" type="button" aria-label="Yopish" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <form className="profileModalContent" onSubmit={handleSubmit}>
          {!isTelegram && (
            <div className="statusPanel youtubeConnectionStatus">
              <div className="statusTitle">
                <YouTubeIcon size={18} />
                <strong>Rasmiy YouTube kanal ulanishi</strong>
              </div>
              <div className="statusGrid">
                <span>Tanlangan brand</span>
                <strong>{selectedBrandName || "Brand tanlanmagan"}</strong>
                <span>YouTube API</span>
                <strong>{youtubeStatus ? (youtubeStatus.configured ? "Tayyor" : "Sozlanmagan") : "Tekshirilmoqda"}</strong>
                <span>Source turi</span>
                <strong>Owned · kanal</strong>
              </div>
              {!selectedBrandId && <p className="statusWarning">Official kanal ulashdan oldin brandni tanlang.</p>}
              {youtubeStatus && !youtubeStatus.configured && (
                <p className="statusWarning">Kanal katalogga saqlanadi, ammo API key sozlanmaguncha resolve va sync ishlamaydi.</p>
              )}
              {isEdit && source?.source_kind !== "channel" && (
                <p className="statusWarning">Bu eski source kanal emas. Uni official kanalga almashtirish uchun yangi kanal manzilini kiriting.</p>
              )}
            </div>
          )}

          {formError && <div className="errorBanner compact">{formError}</div>}

          <div className="profileModalGrid">
            <div className="profileModalColumn">
              {isTelegram ? (
                <label className="field">
                  <span>Telegram link yoki ID</span>
                  <input
                    className="input"
                    value={form.ref}
                    onChange={(event) => setForm((current) => ({ ...current, ref: event.target.value }))}
                    required
                  />
                </label>
              ) : (
                <>
                  <label className="field">
                    <span>Kanal URL</span>
                    <input
                      className="input"
                      value={form.youtubeChannelUrl}
                      onChange={(event) => updateYoutubeField("url", event.target.value)}
                      placeholder="https://youtube.com/@brand"
                    />
                    <p className="fieldHint">Public /@handle, /channel/UC... yoki legacy /user/... link.</p>
                  </label>
                  <label className="field">
                    <span>@handle</span>
                    <input
                      className="input"
                      value={form.youtubeHandle}
                      onChange={(event) => updateYoutubeField("handle", event.target.value)}
                      placeholder="@brand"
                    />
                    <p className="fieldHint">Kanal URL o'rniga rasmiy handle qiymatini kiriting.</p>
                  </label>
                  <label className="field">
                    <span>Channel ID</span>
                    <input
                      className="input"
                      value={form.youtubeChannelId}
                      onChange={(event) => updateYoutubeField("id", event.target.value)}
                      placeholder="UC..."
                    />
                    <p className="fieldHint">UC bilan boshlanadigan 24 belgili channel ID.</p>
                  </label>
                </>
              )}
              <label className="field">
                <span>Ko'rinadigan nom</span>
                <input
                  className="input"
                  value={form.displayName}
                  onChange={(event) => setForm((current) => ({ ...current, displayName: event.target.value }))}
                />
              </label>
              <label className="field">
                <span>Kuzatuv sanasi</span>
                <input
                  className="input"
                  type="date"
                  value={form.monitorFrom}
                  onChange={(event) => setForm((current) => ({ ...current, monitorFrom: event.target.value }))}
                  required
                />
              </label>
            </div>

            <div className="profileModalColumn">
              <div className="profileSwitchGroup">
                <label>
                  <input
                    type="checkbox"
                    checked={form.active}
                    onChange={(event) => setForm((current) => ({ ...current, active: event.target.checked }))}
                  />
                  <span>Kuzatuv active</span>
                </label>
                {isTelegram ? (
                  <>
                    <label>
                      <input
                        type="checkbox"
                        checked={form.collectPosts}
                        onChange={(event) => setForm((current) => ({ ...current, collectPosts: event.target.checked }))}
                      />
                      <span>Postlarni olish</span>
                    </label>
                    <label>
                      <input
                        type="checkbox"
                        checked={form.collectComments}
                        onChange={(event) => setForm((current) => ({ ...current, collectComments: event.target.checked }))}
                      />
                      <span>Comment/chat olish</span>
                    </label>
                  </>
                ) : (
                  <>
                    <label>
                      <input
                        type="checkbox"
                        checked={form.collectVideos}
                        onChange={(event) => setForm((current) => ({ ...current, collectVideos: event.target.checked }))}
                      />
                      <span>Videolarni olish</span>
                    </label>
                    <label>
                      <input
                        type="checkbox"
                        checked={form.collectComments}
                        onChange={(event) => setForm((current) => ({ ...current, collectComments: event.target.checked }))}
                      />
                      <span>Commentlarni olish</span>
                    </label>
                  </>
                )}
              </div>

              {!isTelegram && (
                <label className="field">
                  <span>Hashtaglar</span>
                  <div className="hashtagComposer compactComposer">
                    <input
                      className="input"
                      value={form.hashtagInput}
                      onChange={(event) => setForm((current) => ({ ...current, hashtagInput: event.target.value }))}
                      onKeyDown={handleHashtagKeyDown}
                      onBlur={addHashtags}
                    />
                    <button className="miniButton" type="button" onClick={addHashtags}>
                      <Hash size={15} />
                      <span>Qo'shish</span>
                    </button>
                  </div>
                  {!!form.hashtags.length && (
                    <div className="hashtagBadges">
                      {form.hashtags.map((tag) => (
                        <span className="sourceTag" key={tag}>
                          {tag}
                          <button
                            type="button"
                            onClick={() => setForm((current) => ({ ...current, hashtags: current.hashtags.filter((item) => item !== tag) }))}
                            aria-label={`${tag} hashtagni olib tashlash`}
                          >
                            <X size={12} />
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                </label>
              )}
            </div>
          </div>

          <label className="field full">
            <span>Ichki izoh</span>
            <textarea
              className="input textarea"
              rows="3"
              value={form.notes}
              onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
            />
          </label>

          {isEdit && refChanged && (
            <div className="profileWarning">
              <AlertCircle size={16} />
              <span>Link o'zgargani uchun bu amal almashtirish sifatida bajariladi.</span>
            </div>
          )}

          {result && (
            <div className={result.ok ? "backfillResult ok" : "backfillResult bad"}>
              <strong>{result.ok ? "Amal bajarildi" : "Amal bajarilmadi"}</strong>
              {result.message && <span>{result.message}</span>}
            </div>
          )}

          <div className="buttonRow profileModalActions">
            <button className="button secondary" type="button" onClick={onClose}>
              Bekor qilish
            </button>
            <button className="button primary" type="submit" disabled={saving || (!isTelegram && !selectedBrandId)}>
              <Save size={17} />
              <span>{saving ? "Saqlanmoqda..." : "Saqlash"}</span>
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

export function Profile() {
  const { t, i18n } = useTranslation();
  const [session, setSession] = useState(() => readAdminSession());
  const [botStatus, setBotStatus] = useState(null);
  const [brands, setBrands] = useState([]);
  const [taxonomy, setTaxonomy] = useState(null);
  const [telegramSources, setTelegramSources] = useState([]);
  const [telegramConnection, setTelegramConnection] = useState(null);
  const [youtubeSources, setYoutubeSources] = useState([]);
  const [youtubeStatus, setYoutubeStatus] = useState(null);
  const [instagramSources, setInstagramSources] = useState([]);
  const [facebookSources, setFacebookSources] = useState([]);
  const [selectedBrandId, setSelectedBrandId] = useState(() => readSelectedBrandId());
  const [selectedPlatform, setSelectedPlatform] = useState("telegram");
  const [modal, setModal] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [unlockBrandTarget, setUnlockBrandTarget] = useState(null);

  const loadProfile = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const requests = await Promise.allSettled([
        endpoints.botStatus(),
        endpoints.brands(),
        endpoints.brandTaxonomy(),
        endpoints.sources(),
        endpoints.youtubeSources(),
        endpoints.instagramSources(),
        endpoints.facebookSources(),
        endpoints.youtubeStatus(),
      ]);
      const value = (index, fallback) => requests[index].status === "fulfilled" ? requests[index].value : fallback;
      const brandRows = value(1, []);
      setBotStatus(value(0, null));
      setBrands(brandRows);
      setTaxonomy(value(2, null));
      setTelegramSources(value(3, []));
      setYoutubeSources(value(4, []));
      setInstagramSources(value(5, []));
      setFacebookSources(value(6, []));
      setYoutubeStatus(value(7, null));
      setSelectedBrandId((current) => {
        const resolved = resolveSelectedBrandId(brandRows, current);
        const brand = brandRows.find((row) => row.id === resolved);
        if (brand?.requires_unlock && !isBrandUnlocked(brand.id)) {
          // Keep list visible, but do not open another client's workspace until unlock.
          setUnlockBrandTarget(brand);
          saveSelectedBrandId("");
          return "";
        }
        return resolved;
      });
      const failed = requests
        .map((request, index) => request.status === "rejected" ? [index, request.reason?.message] : null)
        .filter(Boolean);
      if (failed.length) {
        const labels = ["Telegram status", "Brandlar", "Taxonomy", "Telegram", "YouTube", "Instagram", "Facebook", "YouTube API status"];
        setError(`Qisman yuklandi: ${failed.map(([index]) => labels[index]).join(", ")}. Qolgan bo'limlar ishlashda davom etadi.`);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  // Reload localized taxonomy when UI language changes (uz/en/ru).
  useEffect(() => {
    let cancelled = false;
    endpoints.brandTaxonomy()
      .then((rows) => {
        if (!cancelled) setTaxonomy(rows);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [i18n.resolvedLanguage, i18n.language]);

  useEffect(() => {
    if (!selectedBrandId) {
      setTelegramConnection(null);
      return undefined;
    }
    let cancelled = false;
    setTelegramConnection(null);
    endpoints.telegramConnection(selectedBrandId)
      .then((connection) => {
        if (!cancelled) setTelegramConnection(connection);
      })
      .catch(() => {
        if (!cancelled) setTelegramConnection(null);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedBrandId]);

  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === "Escape") setModal(null);
    }
    if (modal) window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [modal]);

  const selectedBrand = brands.find((brand) => brand.id === selectedBrandId);
  const officialTelegramSources = useMemo(
    () => telegramSources.filter((source) => isOwnedSource(source, selectedBrandId)),
    [telegramSources, selectedBrandId],
  );
  const officialYoutubeSources = useMemo(
    () => youtubeSources.filter(
      (source) => isOwnedSource(source, selectedBrandId) && source.source_kind === "channel",
    ),
    [youtubeSources, selectedBrandId],
  );
  const telegramConnectorConnection = useMemo(
    () => ({
      sources: telegramSources.filter(
        (source) => source.brand_id === selectedBrandId && source.connector_managed,
      ),
    }),
    [telegramSources, selectedBrandId],
  );
  const officialInstagramSources = useMemo(
    () => instagramSources.filter((source) => isOwnedSource(source, selectedBrandId)),
    [instagramSources, selectedBrandId],
  );
  const officialFacebookSources = useMemo(
    () => facebookSources.filter((source) => isOwnedSource(source, selectedBrandId)),
    [facebookSources, selectedBrandId],
  );

  function handleSaveSession(nextSession) {
    saveAdminSession(nextSession);
    setSession(nextSession);
    setResult({ ok: true, message: "Admin profil ma'lumotlari saqlandi." });
  }

  function handleLogout() {
    logout();
  }

  function brandNeedsUnlock(brand) {
    if (!brand?.id || !isSuperAdmin()) return false;
    if (!brand.requires_unlock) return false;
    return !isBrandUnlocked(brand.id);
  }

  function handleBrandChange(brandId) {
    const next = brands.find((brand) => brand.id === brandId);
    if (next && brandNeedsUnlock(next)) {
      setUnlockBrandTarget(next);
      return;
    }
    saveSelectedBrandId(brandId);
    setSelectedBrandId(brandId);
    setTelegramConnection(null);
    setResult(null);
  }

  function handleUnlockSuccess(brandId) {
    setUnlockBrandTarget(null);
    saveSelectedBrandId(brandId);
    setSelectedBrandId(brandId);
    setTelegramConnection(null);
    setResult({ ok: true, message: t("Brand ochildi. Client ish maydoniga kirdingiz.") });
  }

  function handleNewBrand() {
    setSelectedBrandId("");
    setResult(null);
  }

  async function reloadTelegramConnection(brandId = selectedBrandId) {
    if (!brandId) {
      setTelegramConnection(null);
      return null;
    }
    const connection = await endpoints.telegramConnection(brandId);
    if (brandId === selectedBrandId) setTelegramConnection(connection);
    return connection;
  }

  async function handleSaveBrand(brandId, payload) {
    setSaving(true);
    setResult(null);
    try {
      const updated = await endpoints.updateBrand(brandId, payload);
      setBrands((current) => current.map((brand) => (brand.id === updated.id ? updated : brand)));
      saveSelectedBrandId(updated.id);
      setSelectedBrandId(updated.id);
      setResult({ ok: true, message: "Brand intelligence saqlandi. Keyingi mentionlar shu kriteriyalar bilan tahlil qilinadi." });
    } catch (err) {
      setResult({ ok: false, message: err.message });
    } finally {
      setSaving(false);
    }
  }

  async function handleCreateBrand(payload) {
    setSaving(true);
    setResult(null);
    try {
      const created = await endpoints.createBrand(payload);
      setBrands((current) => [created, ...current]);
      saveSelectedBrandId(created.id);
      setSelectedBrandId(created.id);
      setResult({ ok: true, message: "Brand yaratildi. Endi official source'larni shu brandga ulash mumkin." });
    } catch (err) {
      setResult({ ok: false, message: err.message });
    } finally {
      setSaving(false);
    }
  }

  async function handleToggle(platform, source) {
    if (platform === "telegram") {
      await endpoints.updateSource(source.id, { active: !source.active });
    } else {
      await endpoints.youtubeUpdateSource(source.id, { active: !source.active });
    }
    await loadProfile();
    if (platform === "telegram") await reloadTelegramConnection(source.brand_id || selectedBrandId);
  }

  async function handleRefresh(platform, source) {
    setResult(null);
    try {
      if (platform === "telegram") {
        const refresh = await endpoints.refreshSource(source.id);
        setResult({ ok: true, message: `${refresh.source?.title || "Telegram source"} refresh qilindi.` });
      } else {
        const sync = await endpoints.youtubeSyncSource(source.id, { max_pages: 1, comments_per_video: 100 });
        setResult({ ok: sync.ok, message: `Videos: ${sync.videos_seen || 0}, comments: ${sync.comments_seen || 0}` });
      }
    } catch (err) {
      setResult({ ok: false, message: err.message });
    }
    await loadProfile();
    if (platform === "telegram") await reloadTelegramConnection(source.brand_id || selectedBrandId);
  }

  function handleDeleteSource(platform, source) {
    const display = platform === "telegram" || platform === "youtube"
      ? sourceDisplay(platform, source)
      : metaSourceDisplay(platform, source);
    setPendingDelete({ platform, source, title: display.title });
  }

  async function confirmDeleteSource(purgeMentions) {
    if (!pendingDelete) return;
    const { platform, source } = pendingDelete;
    const deleteEndpoint = {
      telegram: endpoints.deleteSource,
      youtube: endpoints.youtubeDeleteSource,
      instagram: endpoints.instagramDeleteSource,
      facebook: endpoints.facebookDeleteSource,
    }[platform];
    if (!deleteEndpoint) return;

    setSaving(true);
    setResult(null);
    try {
      const deleted = await deleteEndpoint(source.id, purgeMentions);
      setResult({
        ok: true,
        message: purgeMentions
          ? `${deleted.sources_deleted} ta source, ${deleted.mentions_deleted} ta post/comment va ${deleted.analyses_deleted} ta AI tahlil butunlay o'chirildi.`
          : `${deleted.sources_deleted} ta source o'chirildi. ${deleted.mentions_retained} ta tahlil qilingan mention saqlandi — bu manbani qayta ulasangiz ular qayta tahlil qilinmaydi.`,
      });
      setPendingDelete(null);
      await loadProfile();
      if (platform === "telegram") await reloadTelegramConnection(source.brand_id || selectedBrandId);
    } catch (err) {
      setResult({ ok: false, message: err.message });
    } finally {
      setSaving(false);
    }
  }

  async function saveTelegramSource(payload) {
    const shouldReplace = payload.mode !== "edit" || payload.refChanged;
    if (!shouldReplace && payload.source?.id) {
      await endpoints.updateSource(payload.source.id, {
        source_category: "owned",
        monitoring_mode: "all_messages",
        competitor_name: payload.displayName || null,
        notes: payload.notes || null,
        collect_posts: payload.collectPosts,
        collect_comments: payload.collectComments,
        active: payload.active,
        monitor_from: payload.monitorFrom,
      });
      return "Telegram source yangilandi.";
    }

    const rows = csvLine([payload.ref, "owned", "all_messages", payload.displayName, payload.notes, payload.monitorFrom]);
    const importResult = await endpoints.importSources({
      brand_id: payload.selectedBrandId || null,
      raw_text: rows,
      default_source_category: "owned",
      default_monitoring_mode: "all_messages",
      default_monitor_from: payload.monitorFrom,
      collect_posts: payload.collectPosts,
      collect_comments: payload.collectComments,
    });
    const imported = importResult.find((row) => row.source?.id)?.source;
    if (!imported?.id) {
      const failed = importResult.find((row) => row.error);
      throw new Error(failed?.error || "Telegram source import qilinmadi.");
    }
    if (imported?.id) {
      try {
        await endpoints.refreshSource(imported.id);
      } catch {
        // Import is still useful even if Bot API access refresh fails.
      }
    }
    if (payload.source?.id && payload.source.id !== imported?.id) {
      await endpoints.updateSource(payload.source.id, {
        active: false,
        notes: payload.source.notes || "Replaced from profile source registry.",
      });
    }
    return payload.source?.id ? "Telegram official source almashtirildi." : "Telegram official source qo'shildi.";
  }

  async function saveYoutubeSource(payload) {
    const shouldReplace = payload.mode !== "edit" || payload.refChanged;
    if (!shouldReplace && payload.source?.id) {
      await endpoints.youtubeUpdateSource(payload.source.id, {
        source_category: "owned",
        monitoring_mode: "all_messages",
        nickname: payload.displayName || null,
        competitor_name: payload.displayName || null,
        hashtags: payload.hashtags,
        notes: payload.notes || null,
        collect_videos: payload.collectVideos,
        collect_comments: payload.collectComments,
        collect_transcripts: payload.collectTranscripts,
        active: payload.active,
        monitor_from: payload.monitorFrom,
      });
      return "YouTube source yangilandi.";
    }

    const rows = csvLine([payload.ref, "owned", "all_messages", payload.displayName, payload.notes, payload.monitorFrom, payload.hashtags.join(" ")]);
    const importResult = await endpoints.youtubeImportSources({
      brand_id: payload.selectedBrandId || null,
      official_channel_only: true,
      raw_text: rows,
      default_source_category: "owned",
      default_monitoring_mode: "all_messages",
      default_monitor_from: payload.monitorFrom,
      default_hashtags: payload.hashtags,
      collect_videos: payload.collectVideos,
      collect_comments: payload.collectComments,
      collect_transcripts: payload.collectTranscripts,
    });
    const imported = importResult.find((row) => row.source?.id)?.source;
    if (!imported?.id) {
      const failed = importResult.find((row) => row.error);
      throw new Error(failed?.error || "YouTube source import qilinmadi.");
    }
    let syncWarning = "";
    if (imported?.id) {
      try {
        const sync = await endpoints.youtubeSyncSource(imported.id, { max_pages: 1, comments_per_video: 100 });
        if (sync.ok === false) syncWarning = sync.error || "YouTube sync ishlamadi.";
      } catch (err) {
        syncWarning = err.message || "YouTube sync ishlamadi.";
      }
    }
    if (payload.source?.id && payload.source.id !== imported?.id) {
      await endpoints.youtubeUpdateSource(payload.source.id, {
        active: false,
        notes: payload.source.notes || "Replaced from profile source registry.",
      });
    }
    const message = payload.source?.id ? "YouTube official source almashtirildi." : "YouTube official source qo'shildi.";
    return syncWarning ? `${message} Source saqlandi, lekin sync ogohlantirishi: ${syncWarning}` : message;
  }

  async function handleSaveSource(payload) {
    setSaving(true);
    setResult(null);
    try {
      if (!payload.selectedBrandId) throw new Error("Official source ulashdan oldin brandni tanlang.");
      if (payload.platform === "telegram" && payload.telegramSetup) {
        const response = await endpoints.telegramSetup(payload.selectedBrandId, payload.telegramSetup);
        setTelegramConnection(response);
        const success = {
          ...response,
          ok: true,
          message: "Telegram bot, kanal va discussion sozlamalari saqlandi.",
        };
        setResult(success);
        await loadProfile();
        return success;
      }

      const message = payload.platform === "telegram"
        ? await saveTelegramSource(payload)
        : await saveYoutubeSource(payload);
      const success = { ok: true, message };
      setResult(success);
      setModal(null);
      await loadProfile();
      return success;
    } catch (err) {
      const failure = { ok: false, message: err.message };
      setResult(failure);
      return failure;
    } finally {
      setSaving(false);
    }
  }

  if (!session) {
    return (
      <div className="appShell">
        <Sidebar botStatus={botStatus} activePath="/profile" />
        <main className="main">
          <section className="panel loginPromptPanel">
            <div>
              <span className="brandPulse" />
              <h1>Profil uchun kirish kerak</h1>
              <p>Admin telefon, login va source registry boshqaruvi login sahifasidan boshlanadi.</p>
            </div>
            <a className="button primary linkButton" href="/login">Login sahifasiga o'tish</a>
          </section>
        </main>
      </div>
    );
  }

  const isInitialLoading = loading && !brands.length;

  return (
    <div className="appShell">
      <Sidebar botStatus={botStatus} activePath="/profile" />
      <main className="main">
        <PageHeader
          eyebrow="Brand source registry"
          title="Profil va official source"
          loading={isInitialLoading}
        />

        {error && <div className="errorBanner">{error}</div>}
        {result && !modal && (
          <div className={result.ok ? "loadingBar success" : "errorBanner"}>
            {result.message}
          </div>
        )}

        <ActiveBrandSelector
          brands={brands}
          selectedBrandId={selectedBrandId}
          onChange={handleBrandChange}
          onCreate={handleNewBrand}
        />

        <ProfileSummary
          telegramSources={officialTelegramSources}
          youtubeSources={officialYoutubeSources}
          instagramSources={officialInstagramSources}
          facebookSources={officialFacebookSources}
          selectedBrandName={selectedBrand?.name}
        />

        <BrandIntelligencePanel
          brand={selectedBrand}
          taxonomy={taxonomy}
          onSave={handleSaveBrand}
          onCreate={handleCreateBrand}
          saving={saving}
        />

        <section className="profileLayout">
          <AdminIdentityPanel session={session} onSave={handleSaveSession} onLogout={handleLogout} />

          <article className="panel profileModelPanel">
            <div className="sectionHeader compact">
              <div>
                <h2><ShieldCheck size={18} /> Source registry modeli</h2>
                <p>Brand official kanali o'zgarsa yangi source qo'shiladi, eski source pause bo'ladi.</p>
              </div>
            </div>
            <div className="registryModelSteps">
              <span><strong>1</strong> Brand admini official linkni kiritadi.</span>
              <span><strong>2</strong> Platform API source'ni resolve qiladi.</span>
              <span><strong>3</strong> Worker yangi post/commentlarni import qiladi.</span>
              <span><strong>4</strong> Dashboard umumiy va platform kesimida analiz qiladi.</span>
            </div>
            <div className="platformPlaybooks">
              {Object.entries(taxonomy?.source_playbooks || {}).map(([platform, steps]) => (
                <article className="playbookCard" key={platform}>
                  <strong>{platform}</strong>
                  {steps.map((step) => <span key={step}>{step}</span>)}
                </article>
              ))}
            </div>
          </article>
        </section>

        <section className="profileSourceWorkspace">
          <div className="profilePlatformTabs">
            {platformTabs.map((item) => {
              const Icon = item.icon;
              const count = item.key === "telegram"
                ? officialTelegramSources.length
                : item.key === "youtube"
                ? officialYoutubeSources.length
                : item.key === "instagram"
                ? officialInstagramSources.length
                : officialFacebookSources.length;
              return (
                <button
                  className={selectedPlatform === item.key ? `active ${item.tone}` : item.tone}
                  type="button"
                  key={item.key}
                  onClick={() => setSelectedPlatform(item.key)}
                >
                  <Icon size={18} />
                  <span>{item.label}</span>
                  <strong>{count}</strong>
                </button>
              );
            })}
          </div>

          <PlatformRegistry
            platform={selectedPlatform}
            telegramSources={officialTelegramSources}
            telegramConnection={telegramConnection}
            youtubeSources={officialYoutubeSources}
            youtubeStatus={youtubeStatus}
            instagramSources={officialInstagramSources}
            facebookSources={officialFacebookSources}
            onOpenCreate={(platform) => {
              setResult(null);
              setModal({ mode: "create", platform, source: null });
            }}
            onOpenEdit={(platform, source) => {
              setResult(null);
              setModal({ mode: "edit", platform, source });
            }}
            onOpenReplace={(platform, source) => {
              setResult(null);
              setModal({ mode: "replace", platform, source });
            }}
            onToggle={handleToggle}
            onRefresh={handleRefresh}
            onDelete={handleDeleteSource}
          />
        </section>

        {modal && (
          <SourceEditorModal
            mode={modal.mode}
            platform={modal.platform}
            source={modal.source}
            selectedBrandId={selectedBrandId}
            selectedBrandName={selectedBrand?.name || ""}
            telegramInitialConnection={telegramConnection || telegramConnectorConnection}
            youtubeStatus={youtubeStatus}
            onClose={() => setModal(null)}
            onSave={handleSaveSource}
            saving={saving}
            result={result}
          />
        )}

        <DeleteSourceModal
          open={Boolean(pendingDelete)}
          sourceName={pendingDelete?.title || ""}
          busy={saving}
          onCancel={() => setPendingDelete(null)}
          onConfirm={confirmDeleteSource}
        />

        {unlockBrandTarget ? (
          <BrandUnlockModal
            brand={unlockBrandTarget}
            onCancel={() => setUnlockBrandTarget(null)}
            onUnlocked={handleUnlockSuccess}
          />
        ) : null}
      </main>
    </div>
  );
}

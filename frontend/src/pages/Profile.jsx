import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  CalendarClock,
  CheckCircle2,
  ExternalLink,
  Hash,
  Link2,
  LogOut,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Save,
  ShieldCheck,
  UserCog,
  X,
} from "lucide-react";
import { endpoints } from "../api/client";
import { TelegramIcon, YouTubeIcon } from "../components/BrandIcons";
import { PageHeader } from "../components/PageHeader";
import { Sidebar } from "../components/Sidebar";
import { clearAdminSession, readAdminSession, saveAdminSession } from "./Login";

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
    key: "future",
    label: "Instagram/Facebook",
    icon: ShieldCheck,
    tone: "planned",
    description: "Keyingi social platformalar uchun registry joyi.",
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

function countActive(items) {
  return items.filter((item) => item.active).length;
}

function sourceCategory(source) {
  return source.source_category || "unknown";
}

function isOwnedSource(source, brandId) {
  if (brandId && source.brand_id !== brandId) return false;
  return sourceCategory(source) === "owned";
}

function ProfileSummary({ telegramSources, youtubeSources, selectedBrandName }) {
  const total = telegramSources.length + youtubeSources.length;
  const active = countActive(telegramSources) + countActive(youtubeSources);
  const paused = total - active;
  const cards = [
    { label: "Brand", value: selectedBrandName || "Tanlanmagan", icon: UserCog, tone: "profile" },
    { label: "Official source", value: total, icon: ShieldCheck, tone: "total" },
    { label: "Active", value: active, icon: CheckCircle2, tone: "source" },
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

function AdminIdentityPanel({ session, onSave, onLogout }) {
  const [form, setForm] = useState({
    display_name: session?.display_name || session?.login || "",
    login: session?.login || "",
    phone: session?.phone || "",
  });

  useEffect(() => {
    setForm({
      display_name: session?.display_name || session?.login || "",
      login: session?.login || "",
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
          <p>Login egasi va Telegram telefon raqami alohida saqlanadi.</p>
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
            placeholder="Profil egasi ismi yoki roli yoziladi"
          />
        </label>
        <label className="field">
          <span>Login</span>
          <input
            className="input"
            value={form.login}
            onChange={(event) => setForm((current) => ({ ...current, login: event.target.value }))}
            placeholder="Admin login nomini kiriting"
          />
        </label>
        <label className="field">
          <span>Telegram telefon</span>
          <input
            className="input"
            value={form.phone}
            onChange={(event) => setForm((current) => ({ ...current, phone: event.target.value }))}
            placeholder="+998901234567 formatida Telegram raqam kiriting"
          />
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
  youtubeSources,
  onOpenCreate,
  onOpenEdit,
  onOpenReplace,
  onToggle,
  onRefresh,
}) {
  const isTelegram = platform === "telegram";
  const sources = isTelegram ? telegramSources : youtubeSources;
  const meta = platformTabs.find((item) => item.key === platform) || platformTabs[0];
  const Icon = meta.icon;

  if (platform === "future") {
    return (
      <article className="panel profileRegistryPanel emptyRegistry">
        <div className="registryEmptyIcon">
          <ShieldCheck size={22} />
        </div>
        <div>
          <h2>Keyingi platformalar</h2>
          <p>Instagram, Facebook va boshqa app'lar ham shu source registry modelida ulanadi: brand profile ichida official linklar, platform worker esa alohida access bilan ishlaydi.</p>
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
              onEdit={() => onOpenEdit(platform, source)}
              onReplace={() => onOpenReplace(platform, source)}
              onToggle={() => onToggle(platform, source)}
              onRefresh={() => onRefresh(platform, source)}
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

function ProfileSourceCard({ platform, source, onEdit, onReplace, onToggle, onRefresh }) {
  const display = sourceDisplay(platform, source);
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
        <em className={statusClass(source)}>{sourceStatus(source)}</em>
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

function SourceEditorModal({ mode, platform, source, selectedBrandId, onClose, onSave, saving, result }) {
  const isTelegram = platform === "telegram";
  const isReplace = mode === "replace";
  const isEdit = mode === "edit";
  const display = sourceDisplay(platform, source);
  const [form, setForm] = useState(() => ({
    ref: isTelegram ? telegramRef(source) : youtubeRef(source),
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

  const title = isEdit ? "Official source tahrirlash" : isReplace ? "Official source almashtirish" : "Official source qo'shish";
  const sourceLabel = isTelegram ? "Telegram link yoki ID" : "YouTube kanal/video linki";
  const refChanged = form.ref.trim() && form.ref.trim() !== display.ref;

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
    if (!form.ref.trim()) return;
    onSave({
      mode,
      platform,
      source,
      selectedBrandId,
      ref: form.ref.trim(),
      refChanged,
      displayName: form.displayName.trim(),
      notes: form.notes.trim(),
      monitorFrom: form.monitorFrom,
      active: form.active,
      collectPosts: form.collectPosts,
      collectComments: form.collectComments,
      collectVideos: form.collectVideos,
      collectTranscripts: form.collectTranscripts,
      hashtags: uniqueHashtags([...form.hashtags, ...splitHashtags(form.hashtagInput)]),
    });
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
          <div className="profileModalGrid">
            <div className="profileModalColumn">
              <label className="field">
                <span>{sourceLabel}</span>
                <input
                  className="input"
                  value={form.ref}
                  onChange={(event) => setForm((current) => ({ ...current, ref: event.target.value }))}
                  placeholder={isTelegram ? "@kanal, t.me/link yoki chat ID kiriting" : "YouTube kanal handle/linki yoki video linkini kiriting"}
                  required
                />
              </label>
              <label className="field">
                <span>Ko'rinadigan nom</span>
                <input
                  className="input"
                  value={form.displayName}
                  onChange={(event) => setForm((current) => ({ ...current, displayName: event.target.value }))}
                  placeholder="Dashboardda ko'rinadigan ichki nomni yozing"
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
                    <label>
                      <input
                        type="checkbox"
                        checked={form.collectTranscripts}
                        onChange={(event) => setForm((current) => ({ ...current, collectTranscripts: event.target.checked }))}
                      />
                      <span>Transcript belgilash</span>
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
                      placeholder="#brand yoki keyword hashtaglarini kiriting"
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
              placeholder="Access, role yoki monitoring maqsadi haqida qisqa izoh yozing"
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
            <button className="button primary" type="submit" disabled={saving}>
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
  const [session, setSession] = useState(() => readAdminSession());
  const [botStatus, setBotStatus] = useState(null);
  const [brands, setBrands] = useState([]);
  const [telegramSources, setTelegramSources] = useState([]);
  const [youtubeSources, setYoutubeSources] = useState([]);
  const [selectedBrandId, setSelectedBrandId] = useState("");
  const [selectedPlatform, setSelectedPlatform] = useState("telegram");
  const [modal, setModal] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const loadProfile = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [bot, brandRows, telegramRows, youtubeRows] = await Promise.all([
        endpoints.botStatus(),
        endpoints.brands(),
        endpoints.sources(),
        endpoints.youtubeSources(),
      ]);
      setBotStatus(bot);
      setBrands(brandRows);
      setTelegramSources(telegramRows);
      setYoutubeSources(youtubeRows);
      setSelectedBrandId((current) => current || (brandRows.length ? brandRows[0].id : ""));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

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
    () => youtubeSources.filter((source) => isOwnedSource(source, selectedBrandId)),
    [youtubeSources, selectedBrandId],
  );

  function handleSaveSession(nextSession) {
    saveAdminSession(nextSession);
    setSession(nextSession);
    setResult({ ok: true, message: "Admin profil ma'lumotlari saqlandi." });
  }

  function handleLogout() {
    clearAdminSession();
    window.location.href = "/login";
  }

  async function handleToggle(platform, source) {
    if (platform === "telegram") {
      await endpoints.updateSource(source.id, { active: !source.active });
    } else {
      await endpoints.youtubeUpdateSource(source.id, { active: !source.active });
    }
    await loadProfile();
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
    if (imported?.id) {
      try {
        await endpoints.youtubeSyncSource(imported.id, { max_pages: 1, comments_per_video: 100 });
      } catch {
        // Source registry update should not be blocked by sync quota/access errors.
      }
    }
    if (payload.source?.id && payload.source.id !== imported?.id) {
      await endpoints.youtubeUpdateSource(payload.source.id, {
        active: false,
        notes: payload.source.notes || "Replaced from profile source registry.",
      });
    }
    return payload.source?.id ? "YouTube official source almashtirildi." : "YouTube official source qo'shildi.";
  }

  async function handleSaveSource(payload) {
    setSaving(true);
    setResult(null);
    try {
      const message = payload.platform === "telegram"
        ? await saveTelegramSource(payload)
        : await saveYoutubeSource(payload);
      setResult({ ok: true, message });
      setModal(null);
      await loadProfile();
    } catch (err) {
      setResult({ ok: false, message: err.message });
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
          brands={brands}
          selectedBrandId={selectedBrandId}
          onBrandChange={setSelectedBrandId}
          onRefresh={loadProfile}
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

        <ProfileSummary
          telegramSources={officialTelegramSources}
          youtubeSources={officialYoutubeSources}
          selectedBrandName={selectedBrand?.name}
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
          </article>
        </section>

        <section className="profileSourceWorkspace">
          <div className="profilePlatformTabs">
            {platformTabs.map((item) => {
              const Icon = item.icon;
              const count = item.key === "telegram" ? officialTelegramSources.length : item.key === "youtube" ? officialYoutubeSources.length : 0;
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
            youtubeSources={officialYoutubeSources}
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
          />
        </section>

        {modal && (
          <SourceEditorModal
            mode={modal.mode}
            platform={modal.platform}
            source={modal.source}
            selectedBrandId={selectedBrandId}
            onClose={() => setModal(null)}
            onSave={handleSaveSource}
            saving={saving}
            result={result}
          />
        )}
      </main>
    </div>
  );
}

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  BarChart3,
  DownloadCloud,
  Hash,
  KeyRound,
  MessageSquareText,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  Trash2,
  Users,
  Video,
  X,
} from "lucide-react";
import { clearApiCache, endpoints, readSelectedBrandId, resolveSelectedBrandId } from "../api/client";
import { YouTubeIcon } from "../components/BrandIcons";
import { MonitoringInsights } from "../components/MonitoringInsights";
import { PageHeader } from "../components/PageHeader";
import { Sidebar } from "../components/Sidebar";
import { StatsBar } from "../components/StatsBar";
import { formatUiDate, translateUiText } from "../i18n";

const categoryIcons = {
  owned: YouTubeIcon,
  competitor: Users,
  keyword: KeyRound,
  hashtag: Hash,
  influencer: Users,
  campaign: BarChart3,
  risk: ShieldAlert,
  unknown: Search,
};

const categoryOrder = ["owned", "competitor", "keyword", "hashtag", "influencer", "campaign", "risk", "unknown"];

const sourceKindLabels = {
  channel: "Kanal",
  video: "Video",
  keyword: "Keyword",
  hashtag: "Hashtag",
  unknown: "Turi noma'lum",
};

const monitoringModeLabels = {
  all_messages: "Barcha ma'lumot",
  brand_matches_only: "Faqat mos kelganlar",
};

const mentionTypeLabels = {
  video: "Video",
  comment: "Comment",
  comment_reply: "Comment reply",
};

const sentimentLabels = {
  positive: "Ijobiy",
  negative: "Salbiy",
  neutral: "Neytral",
  mixed: "Aralash",
};

const riskLabels = {
  low: "Past risk",
  medium: "O'rta risk",
  high: "Yuqori risk",
  critical: "Kritik risk",
};

function todayInputValue() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 10);
}

function sourceRef(source) {
  if (source.channel_handle) return source.channel_handle;
  if (source.channel_id) return source.channel_id;
  if (source.video_id) return source.video_id;
  return source.query || source.source_ref || "unresolved";
}

function sourceTitle(source) {
  return source.nickname || source.title || source.channel_title || source.competitor_name || sourceRef(source);
}

function sourceUrl(source) {
  if (source.video_id) return `https://www.youtube.com/watch?v=${source.video_id}`;
  if (source.channel_handle) return `https://www.youtube.com/${source.channel_handle}`;
  if (source.channel_id) return `https://www.youtube.com/channel/${source.channel_id}`;
  const query = source.query || source.source_ref || "";
  return `https://www.youtube.com/results?search_query=${encodeURIComponent(query)}`;
}

function mentionSource(mention) {
  return mention.channel_title || mention.author_name || mention.video_id || "YouTube";
}

function mentionText(mention) {
  return mention.text || mention.title || "";
}

function formatDate(value) {
  if (!value) return "";
  return formatUiDate(value, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

function sourceKindLabel(value) {
  return translateUiText(sourceKindLabels[value] || value || "Turi noma'lum");
}

function monitoringModeLabel(value) {
  return translateUiText(monitoringModeLabels[value] || value || "Qamrov noma'lum");
}

function mentionTypeLabel(value) {
  return translateUiText(mentionTypeLabels[value] || value || "Mention");
}

function compactNumber(value) {
  if (value === null || value === undefined) return "";
  return new Intl.NumberFormat("uz-UZ", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function mentionMetrics(mention) {
  return [
    mention.view_count !== null && mention.view_count !== undefined ? `views ${compactNumber(mention.view_count)}` : "",
    mention.like_count !== null && mention.like_count !== undefined ? `likes ${compactNumber(mention.like_count)}` : "",
    mention.comment_count !== null && mention.comment_count !== undefined ? `comments ${compactNumber(mention.comment_count)}` : "",
  ].filter(Boolean);
}

function normalizeHashtag(value) {
  const cleaned = value.trim().replace(/^#+/, "").replace(/[,\s;]+/g, "");
  return cleaned ? `#${cleaned.toLowerCase()}` : "";
}

function hashtagOverflowLabel(count) {
  if (count > 10) return "10+";
  if (count > 5) return "5+";
  return "";
}

function mergeHashtags(current, incoming) {
  const next = [...current];
  const seen = new Set(current.map((item) => item.toLowerCase()));
  incoming.forEach((item) => {
    const tag = normalizeHashtag(item);
    if (tag && !seen.has(tag)) {
      seen.add(tag);
      next.push(tag);
    }
  });
  return next;
}

function splitHashtagInput(value) {
  return value.split(/[\s,;]+/).map(normalizeHashtag).filter(Boolean);
}

function HashtagBadges({ tags = [], onRemove, limit = 5 }) {
  if (!tags.length) return null;
  const visible = tags.slice(0, limit);
  const overflow = hashtagOverflowLabel(tags.length);
  return (
    <div className="hashtagBadges">
      {visible.map((tag) => (
        <span className="sourceTag" key={tag}>
          {tag}
          {onRemove && (
            <button type="button" onClick={() => onRemove(tag)} aria-label={`${tag} hashtagni o'chirish`}>
              <X size={12} />
            </button>
          )}
        </span>
      ))}
      {overflow && <span className="sourceTag more">{overflow}</span>}
    </div>
  );
}

export function YoutubeMonitoring() {
  const [botStatus, setBotStatus] = useState(null);
  const [youtubeStatus, setYoutubeStatus] = useState(null);
  const [brands, setBrands] = useState([]);
  const [categories, setCategories] = useState([]);
  const [sources, setSources] = useState([]);
  const [summary, setSummary] = useState(null);
  const [mentions, setMentions] = useState([]);
  const [selectedBrandId, setSelectedBrandId] = useState(() => readSelectedBrandId());
  const [selectedCategoryKey, setSelectedCategoryKey] = useState("owned");
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [sourceResult, setSourceResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const realtimeRefreshTimer = useRef(null);
  const selectedBrandIdRef = useRef("");
  const lastLoadedBrandId = useRef("");

  useEffect(() => {
    selectedBrandIdRef.current = selectedBrandId;
  }, [selectedBrandId]);

  const visibleSources = useMemo(() => {
    if (!selectedBrandId) return sources;
    return sources.filter((source) => source.brand_id === selectedBrandId);
  }, [sources, selectedBrandId]);

  const statItems = useMemo(
    () => [
      { label: "Source", value: visibleSources.length, icon: YouTubeIcon },
      { label: "Mention", value: summary?.mentions_total || 0, icon: MessageSquareText },
      { label: "Comment", value: summary?.comments_total || 0, icon: BarChart3 },
      { label: "High risk", value: summary?.high_risk || 0, icon: ShieldAlert },
    ],
    [summary, visibleSources.length],
  );

  // Stable identity (no deps) so it never re-triggers the SSE effect below.
  const loadDashboard = useCallback(async (brandId) => {
    const activeBrandId = (brandId ?? selectedBrandIdRef.current) || "";
    lastLoadedBrandId.current = activeBrandId;
    const [sourceRows, summaryRow, mentionRows] = await Promise.all([
      endpoints.youtubeSources(),
      endpoints.youtubeSummary(activeBrandId),
      endpoints.youtubeMentions(activeBrandId),
    ]);
    setSources(sourceRows);
    setSummary(summaryRow);
    setMentions(mentionRows);
  }, []);

  const loadInitial = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [bot, status, categoryRows, brandRows] = await Promise.all([
        endpoints.botStatus(),
        endpoints.youtubeStatus(),
        endpoints.youtubeSourceCategories(),
        endpoints.brands(),
      ]);
      setBotStatus(bot);
      setYoutubeStatus(status);
      setCategories(categoryRows);
      setBrands(brandRows);
      const defaultBrandId = resolveSelectedBrandId(brandRows, selectedBrandId);
      if (defaultBrandId && defaultBrandId !== selectedBrandId) {
        setSelectedBrandId(defaultBrandId);
      }
      await loadDashboard(defaultBrandId);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [loadDashboard, selectedBrandId]);

  useEffect(() => {
    loadInitial();
  }, []);

  useEffect(() => {
    if (selectedBrandId === lastLoadedBrandId.current) return;
    loadDashboard(selectedBrandId).catch((err) => setError(err.message));
  }, [selectedBrandId, loadDashboard]);

  // Open the realtime stream once for the page lifetime; brand filtering reads
  // the latest value via a ref so the EventSource is never torn down/reopened.
  useEffect(() => {
    const eventSource = new EventSource(endpoints.eventsUrl());

    function shouldRefresh(event) {
      const activeBrandId = selectedBrandIdRef.current;
      if (!activeBrandId) return true;
      try {
        const payload = JSON.parse(event.data || "{}");
        return !payload.brand_id || payload.brand_id === activeBrandId;
      } catch {
        return true;
      }
    }

    function scheduleRefresh(event) {
      if (!shouldRefresh(event) || realtimeRefreshTimer.current) return;
      realtimeRefreshTimer.current = window.setTimeout(() => {
        realtimeRefreshTimer.current = null;
        clearApiCache("/youtube/");
        loadDashboard(selectedBrandIdRef.current).catch((err) => setError(err.message));
      }, 800);
    }

    eventSource.addEventListener("youtube_mention", scheduleRefresh);
    eventSource.addEventListener("youtube_source", scheduleRefresh);
    eventSource.addEventListener("analysis_updated", scheduleRefresh);

    return () => {
      eventSource.close();
      if (realtimeRefreshTimer.current) {
        window.clearTimeout(realtimeRefreshTimer.current);
        realtimeRefreshTimer.current = null;
      }
    };
  }, [loadDashboard]);

  useEffect(() => {
    if (!categories.length) return;
    const hasSelectedCategory = categories.some((category) => category.key === selectedCategoryKey);
    if (!hasSelectedCategory) setSelectedCategoryKey(categories[0].key);
  }, [categories, selectedCategoryKey]);

  useEffect(() => {
    if (!isAddModalOpen) return undefined;
    function handleKeyDown(event) {
      if (event.key === "Escape") setIsAddModalOpen(false);
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isAddModalOpen]);

  async function handleImport(payload) {
    const result = await endpoints.youtubeImportSources(payload);
    const importedSources = result.map((row) => row.source).filter((source) => source?.id);
    let latest = null;
    for (const source of importedSources) {
      let sync = null;
      try {
        sync = await endpoints.youtubeSyncSource(source.id, { max_pages: 1, comments_per_video: 100 });
      } catch (err) {
        sync = { ok: false, error: err.message, videos_seen: 0, comments_seen: 0 };
      }
      latest = { source, sync };
    }
    if (latest) setSourceResult(latest);
    await loadDashboard(selectedBrandId);
  }

  async function handleToggleSource(source) {
    await endpoints.youtubeUpdateSource(source.id, { active: !source.active });
    await loadDashboard(selectedBrandId);
  }

  async function handleSyncSource(source) {
    const sync = await endpoints.youtubeSyncSource(source.id, { max_pages: 1, comments_per_video: 100 });
    setSourceResult({ source, sync });
    await loadDashboard(selectedBrandId);
  }

  async function handleDeleteSource(source) {
    const confirmed = window.confirm(translateUiText(
      `“${sourceTitle(source)}” source butunlay o'chirilsinmi? Unga tegishli barcha video, comment va AI tahlillar ham o'chadi. Bu amalni ortga qaytarib bo'lmaydi.`,
    ));
    if (!confirmed) return;
    setError("");
    setNotice("");
    try {
      const deleted = await endpoints.youtubeDeleteSource(source.id);
      setNotice(`${deleted.sources_deleted} ta source, ${deleted.mentions_deleted} ta video/comment va ${deleted.analyses_deleted} ta AI tahlil o'chirildi.`);
      await loadDashboard(selectedBrandId);
    } catch (err) {
      setError(err.message || "Source o'chirishda xatolik yuz berdi.");
    }
  }

  const isInitialLoading = loading && !summary && !sources.length && !mentions.length;

  return (
    <div className="appShell">
      <Sidebar botStatus={botStatus} activePath="/youtube-monitoring" />
      <main className="main">
        <PageHeader
          eyebrow="Video source catalog"
          title="YouTube monitoring"
          loading={isInitialLoading}
        />

        {error && <div className="errorBanner">{error}</div>}
        {notice && <div className="loadingBar success">{notice}</div>}
        {youtubeStatus && !youtubeStatus.configured && (
          <div className="loadingBar">YOUTUBE_API_KEY sozlanmagan. Source katalog ishlaydi, avtomatik sync uchun API key kerak.</div>
        )}

        <StatsBar items={statItems} loading={isInitialLoading} />
        <MonitoringInsights
          platform="youtube"
          sources={visibleSources}
          summary={summary}
          status={youtubeStatus}
          loading={isInitialLoading}
        />

        <section className="monitoringWorkspace">
          <YoutubeSourceBoard
            categories={categories}
            sources={visibleSources}
            selectedCategoryKey={selectedCategoryKey}
            onCategoryChange={setSelectedCategoryKey}
            onOpenAdd={() => setIsAddModalOpen(true)}
            onToggleSource={handleToggleSource}
            onSyncSource={handleSyncSource}
            onDeleteSource={handleDeleteSource}
            loading={isInitialLoading}
          />
          <YoutubeRecentMentions mentions={mentions} loading={isInitialLoading} />
        </section>

        {isAddModalOpen && (
          <div className="modalOverlay" role="presentation" onMouseDown={() => setIsAddModalOpen(false)}>
            <section
              className="modalPanel"
              role="dialog"
              aria-modal="true"
              aria-labelledby="add-youtube-source-title"
              onMouseDown={(event) => event.stopPropagation()}
            >
              <div className="modalHeader">
                <div>
                  <h2 id="add-youtube-source-title">YouTube source qo'shish</h2>
                  <p>Channel, video, hashtag yoki keyword qo'shing.</p>
                </div>
                <button className="iconButton" type="button" aria-label="Yopish" onClick={() => setIsAddModalOpen(false)}>
                  <X size={18} />
                </button>
              </div>
              <div className="modalContent">
                <YoutubeSourceForm
                  categories={categories}
                  selectedBrandId={selectedBrandId}
                  initialCategory={selectedCategoryKey}
                  onImport={handleImport}
                  sourceResult={sourceResult}
                />
              </div>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}

function YoutubeSourceBoard({
  categories,
  sources,
  selectedCategoryKey,
  onCategoryChange,
  onOpenAdd,
  onToggleSource,
  onSyncSource,
  onDeleteSource,
  loading = false,
}) {
  const orderedCategories = useMemo(
    () => categories.slice().sort((a, b) => categoryOrder.indexOf(a.key) - categoryOrder.indexOf(b.key)),
    [categories],
  );
  const counts = sources.reduce((acc, source) => {
    const key = source.source_category || "unknown";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const selectedCategory = orderedCategories.find((category) => category.key === selectedCategoryKey) || orderedCategories[0];
  const selectedSources = sources.filter((source) => (source.source_category || "unknown") === selectedCategory?.key);
  const SelectedIcon = categoryIcons[selectedCategory?.key] || Search;

  if (loading) {
    return (
      <section className="folderPanel panel isLoading" aria-busy="true">
        <div className="folderControls">
          <div className="folderSelectField">
            <span className="skeletonText label" />
            <span className="skeletonControl" />
          </div>
          <span className="skeletonButton" />
        </div>
        <div className="selectedFolderInfo skeletonFolderInfo">
          <span className="skeletonIcon folder" />
          <div>
            <span className="skeletonText heading" />
            <span className="skeletonText wide" />
          </div>
          <span className="skeletonPill" />
        </div>
        <div className="sourceList">
          {Array.from({ length: 3 }).map((_, index) => (
            <article className="sourceRow skeletonRow" key={`youtube-source-skeleton-${index}`}>
              <div className="sourceIdentity">
                <span className="skeletonText heading" />
                <span className="skeletonText sm" />
              </div>
              <div className="sourceSignals skeletonChips">
                <span />
                <span />
                <span />
              </div>
              <span className="skeletonPill" />
              <div className="rowActions skeletonActions">
                <span />
                <span />
                <span />
              </div>
            </article>
          ))}
        </div>
      </section>
    );
  }

  return (
    <section className="folderPanel panel">
      <div className="folderControls">
        <label className="folderSelectField">
          <span>YouTube papkalari</span>
          <select
            className="input select"
            value={selectedCategory?.key || ""}
            onChange={(event) => onCategoryChange(event.target.value)}
          >
            {orderedCategories.map((category) => (
              <option key={category.key} value={category.key}>
                {category.label} ({counts[category.key] || 0})
              </option>
            ))}
          </select>
        </label>
        <button className="button primary addSourceButton" type="button" onClick={onOpenAdd}>
          <Plus size={17} />
          <span>Qo'shish</span>
        </button>
      </div>

      {selectedCategory && (
        <div className="selectedFolderInfo">
          <div className="folderIcon">
            <SelectedIcon size={20} />
          </div>
          <div>
            <h2>{selectedCategory.label}</h2>
            <p>{selectedCategory.description}</p>
          </div>
          <span className="pill neutral">{selectedSources.length} source</span>
        </div>
      )}

      <div className="sourceList">
        {selectedSources.length ? (
          selectedSources.map((source) => (
            <YoutubeSourceRow
              key={source.id}
              source={source}
              onToggleSource={onToggleSource}
              onSyncSource={onSyncSource}
              onDeleteSource={onDeleteSource}
            />
          ))
        ) : (
          <div className="empty tall">Bu papkada source yo'q</div>
        )}
      </div>
    </section>
  );
}

function YoutubeSourceRow({ source, onToggleSource, onSyncSource, onDeleteSource }) {
  return (
    <article className="sourceRow">
      <div className="sourceIdentity">
        <strong>{sourceTitle(source)}</strong>
        <span>{sourceRef(source)}</span>
      </div>
      <div className="sourceSignals">
        <span title={source.source_kind || "unknown"}>{sourceKindLabel(source.source_kind)}</span>
        <span className={source.monitoring_mode === "all_messages" ? "accent" : "blue"} title={source.monitoring_mode}>
          {monitoringModeLabel(source.monitoring_mode)}
        </span>
        {source.collect_videos && <span title="Video title, description va metrikalar olinadi">Videolar</span>}
        {source.collect_comments && <span title="Video commentlari olinadi">Commentlar</span>}
        {source.collect_transcripts && <span title="Kelajakdagi transcript/audio pipeline uchun belgi">Transcript</span>}
        {source.uploads_playlist_id && <span className="blue" title="Kanal videolari uploads playlist orqali olinadi">Uploads ulangan</span>}
      </div>
      <HashtagBadges tags={source.hashtags || []} />
      <em className={source.active ? "state ok" : "state neutral"}>{source.active ? "active" : "paused"}</em>
      <div className="rowActions">
        <button className="miniButton" type="button" onClick={() => onSyncSource(source)}>
          <RefreshCw size={15} />
          <span>Sync</span>
        </button>
        <a className="miniButton linkButton" href={sourceUrl(source)} target="_blank" rel="noreferrer">
          <DownloadCloud size={15} />
          <span>Ochish</span>
        </a>
        <button className="miniButton" type="button" onClick={() => onToggleSource(source)}>
          {source.active ? <Pause size={15} /> : <Play size={15} />}
          <span>{source.active ? "Pauza" : "Davom"}</span>
        </button>
        <button className="miniButton danger" type="button" onClick={() => onDeleteSource(source)} title="Source va unga tegishli barcha video, comment hamda AI tahlillarini o'chiradi">
          <Trash2 size={15} />
          <span>O'chirish</span>
        </button>
      </div>
      {(source.notes || source.competitor_name) && <p className="sourceRowNote">{source.notes || source.competitor_name}</p>}
    </article>
  );
}

function YoutubeSourceForm({ categories, selectedBrandId, initialCategory, onImport, sourceResult }) {
  const [nickname, setNickname] = useState("");
  const [channelLink, setChannelLink] = useState("");
  const [hashtagInput, setHashtagInput] = useState("");
  const [hashtags, setHashtags] = useState([]);
  const [category, setCategory] = useState(initialCategory || "owned");
  const [mode, setMode] = useState("brand_matches_only");
  const [monitorFrom, setMonitorFrom] = useState(todayInputValue);
  const [notes, setNotes] = useState("");
  const [collectVideos, setCollectVideos] = useState(true);
  const [collectComments, setCollectComments] = useState(true);
  const [collectTranscripts, setCollectTranscripts] = useState(false);

  useEffect(() => {
    const nextCategory = categories.find((item) => item.key === initialCategory) || categories[0];
    if (!nextCategory) return;
    setCategory(nextCategory.key);
    setMode(nextCategory.default_monitoring_mode);
  }, [categories, initialCategory]);

  function handleCategory(value) {
    const meta = categories.find((item) => item.key === value);
    setCategory(value);
    if (meta) setMode(meta.default_monitoring_mode);
  }

  function addHashtags(value = hashtagInput) {
    const nextTags = splitHashtagInput(value);
    if (!nextTags.length) return;
    setHashtags((current) => mergeHashtags(current, nextTags));
    setHashtagInput("");
  }

  function handleHashtagKeyDown(event) {
    if (event.key === "Enter" || event.key === "," || event.key === "Tab") {
      if (!hashtagInput.trim()) return;
      event.preventDefault();
      addHashtags();
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const nextHashtags = mergeHashtags(hashtags, splitHashtagInput(hashtagInput));
    if (!channelLink.trim() && !nextHashtags.length) return;
    const rows = [];
    if (channelLink.trim()) {
      rows.push([channelLink, category, mode, nickname, notes, monitorFrom, nextHashtags.join(" ")]);
    }
    nextHashtags.forEach((tag) => {
      rows.push([tag, "hashtag", "brand_matches_only", nickname, notes, monitorFrom, tag]);
    });
    const rawText = rows
      .map((row) => row.map((value) => `"${String(value || "").replaceAll('"', '""')}"`).join(","))
      .join("\n");
    await onImport({
      brand_id: selectedBrandId || null,
      raw_text: rawText,
      default_source_category: category,
      default_monitoring_mode: mode,
      default_monitor_from: monitorFrom,
      default_hashtags: nextHashtags,
      collect_videos: collectVideos,
      collect_comments: collectComments,
      collect_transcripts: collectTranscripts,
    });
    setNickname("");
    setChannelLink("");
    setHashtagInput("");
    setHashtags([]);
    setNotes("");
  }

  return (
    <form className="sourceForm" onSubmit={handleSubmit}>
      <div className="panelHeader">
        <div>
          <h2>Manzil qo'shish</h2>
          <p>Kuzatiladigan kanal, video link va hashtaglar.</p>
        </div>
      </div>

      <label className="field">
        <span>Nickname</span>
        <input
          className="input"
          value={nickname}
          onChange={(event) => setNickname(event.target.value)}
        />
        <p className="fieldHint">Dashboardda ko'rinadigan ichki nom. Filterga yordamchi signal sifatida ham ishlaydi.</p>
      </label>

      <label className="field">
        <span>Kanal yoki video link</span>
        <input
          className="input"
          value={channelLink}
          onChange={(event) => setChannelLink(event.target.value)}
        />
        <p className="fieldHint">Kanal handle/linki, video linki yoki YouTube ID kiriting. Kanal bo'lsa videolar uploads playlist orqali olinadi.</p>
      </label>

      <label className="field full">
        <span>Hashtaglar</span>
        <div className="hashtagComposer">
          <input
            className="input"
            value={hashtagInput}
            onChange={(event) => setHashtagInput(event.target.value)}
            onKeyDown={handleHashtagKeyDown}
            onBlur={() => addHashtags()}
          />
          <button className="miniButton" type="button" onClick={() => addHashtags()}>
            <Plus size={15} />
            <span>Hashtag</span>
          </button>
        </div>
        <HashtagBadges tags={hashtags} onRemove={(tag) => setHashtags((current) => current.filter((item) => item !== tag))} />
        <p className="fieldHint">Har bir hashtag alohida watch source bo'ladi va kanal source ichida ham saqlanadi.</p>
      </label>

      <div className="formGrid">
        <label className="field">
          <span>Papka</span>
          <select className="input select" value={category} onChange={(event) => handleCategory(event.target.value)}>
            {categories.map((item) => (
              <option key={item.key} value={item.key}>{item.label}</option>
            ))}
          </select>
          <p className="fieldHint">Source dashboardda qaysi YouTube papkasida turishini belgilaydi.</p>
        </label>
        <label className="field">
          <span>Qamrov</span>
          <select className="input select" value={mode} onChange={(event) => setMode(event.target.value)}>
            <option value="brand_matches_only">{monitoringModeLabel("brand_matches_only")}</option>
            <option value="all_messages">{monitoringModeLabel("all_messages")}</option>
          </select>
          <p className="fieldHint">Faqat hashtag/brand moslari yoki kanalning barcha video/commentlari olinadi.</p>
        </label>
        <label className="field">
          <span>Kuzatuv sanasi</span>
          <input className="input" type="date" value={monitorFrom} onChange={(event) => setMonitorFrom(event.target.value)} required />
          <p className="fieldHint">Sync shu sanadan keyingi video va commentlarni import qiladi.</p>
        </label>
      </div>

      <label className="field full">
        <span>Izoh</span>
        <textarea
          className="input textarea"
          rows="3"
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
        />
        <p className="fieldHint">Source haqida ichki eslatma. Monitoring filtrini o'zgartirmaydi.</p>
      </label>

      <div className="checks">
        <label>
          <input type="checkbox" checked={collectVideos} onChange={(event) => setCollectVideos(event.target.checked)} />
          <span>Videolar</span>
        </label>
        <label>
          <input type="checkbox" checked={collectComments} onChange={(event) => setCollectComments(event.target.checked)} />
          <span>Commentlar</span>
        </label>
        <label>
          <input type="checkbox" checked={collectTranscripts} onChange={(event) => setCollectTranscripts(event.target.checked)} />
          <span>Transcript</span>
        </label>
      </div>

      <button className="button primary fullButton" type="submit">
        <Plus size={17} />
        <span>Qo'shish</span>
      </button>

      {sourceResult?.sync && (
        <div className={sourceResult.sync.ok ? "backfillResult ok" : "backfillResult bad"}>
          <strong>{sourceResult.sync.ok ? "Sync yakunlandi" : "Sync xatolik"}</strong>
          <span>
            Videos: {sourceResult.sync.videos_seen || 0} · Comments: {sourceResult.sync.comments_seen || 0}
          </span>
          {sourceResult.sync.error && <small>{sourceResult.sync.error}</small>}
        </div>
      )}
    </form>
  );
}

function YoutubeRecentMentions({ mentions, loading = false }) {
  const [selectedMention, setSelectedMention] = useState(null);

  return (
    <section className={loading ? "recentSection isLoading" : "recentSection"} aria-busy={loading}>
      <div className="sectionHeader">
        <div>
          {loading ? (
            <>
              <span className="skeletonText heading" />
              <span className="skeletonText wide" />
            </>
          ) : (
            <>
              <h2>Oxirgi YouTube mentionlar</h2>
              <p>Video title, description, comment va keyinchalik transcript oqimi.</p>
            </>
          )}
        </div>
      </div>
      <div className="mentionList">
        {loading ? (
          Array.from({ length: 7 }).map((_, index) => (
            <div className="mentionItem skeletonMention" key={`youtube-mention-skeleton-${index}`}>
              <span className="skeletonIcon" />
              <div className="mentionBody">
                <span className="skeletonText heading" />
                <span className="skeletonText wide" />
                <span className="skeletonText mid" />
              </div>
              <span className="mentionMeta">
                <span className="skeletonText sm" />
                <span className="skeletonText xs" />
              </span>
            </div>
          ))
        ) : mentions.length ? (
          mentions.map((mention) => (
            <button className="mentionItem" type="button" key={mention.id} onClick={() => setSelectedMention(mention)}>
              <div className="mentionIcon">
                {mention.item_type === "video" ? <Video size={18} /> : <MessageSquareText size={18} />}
              </div>
              <div className="mentionBody">
                <strong>{mentionSource(mention)}</strong>
                {mentionText(mention)
                  ? <p data-i18n-ignore="true">{mentionText(mention)}</p>
                  : <p>Matn yo'q</p>}
                {!!mentionMetrics(mention).length && (
                  <div className="mentionMetricRow">
                    {mentionMetrics(mention).map((item) => (
                      <span key={item}>{item}</span>
                    ))}
                  </div>
                )}
                {!!mention.brand_match_terms?.length && <span className="mentionSignal">Brand signal</span>}
                {mention.analysis && !mention.analysis.error ? (
                  <div className="mentionAnalysis">
                    <div className="mentionBadgeRow">
                      {mention.analysis.sentiment && (
                        <span className={`sentimentBadge ${mention.analysis.sentiment}`}>
                          {sentimentLabels[mention.analysis.sentiment] || mention.analysis.sentiment}
                          {typeof mention.analysis.sentiment_score === "number"
                            ? ` · ${mention.analysis.sentiment_score.toFixed(2)}`
                            : ""}
                        </span>
                      )}
                      {mention.analysis.risk_level && (
                        <span className={`riskBadge ${mention.analysis.risk_level}`}>
                          {riskLabels[mention.analysis.risk_level] || mention.analysis.risk_level}
                        </span>
                      )}
                    </div>
                    {mention.analysis.summary && <p className="mentionSummary">{mention.analysis.summary}</p>}
                    {mention.analysis.suggested_action && <p className="mentionAction">{mention.analysis.suggested_action}</p>}
                  </div>
                ) : (
                  <span className="mentionPending">AI tahlil kutilmoqda…</span>
                )}
              </div>
              <span className="mentionMeta">
                <em title={mention.item_type}>{mentionTypeLabel(mention.item_type)}</em>
                <small title="YouTube'da e'lon qilingan vaqt">{formatDate(mention.published_at)}</small>
              </span>
            </button>
          ))
        ) : (
          <div className="empty">YouTube mention yo'q</div>
        )}
      </div>

      {selectedMention && (
        <div className="modalOverlay" role="presentation" onMouseDown={() => setSelectedMention(null)}>
          <section
            className="modalPanel mentionModal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="youtube-mention-detail-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="modalHeader">
              <div>
                <h2 id="youtube-mention-detail-title">{mentionSource(selectedMention)}</h2>
                <p>
                  {mentionTypeLabel(selectedMention.item_type)} · {formatDate(selectedMention.published_at)}
                </p>
              </div>
              <button className="iconButton" type="button" aria-label="Yopish" onClick={() => setSelectedMention(null)}>
                <X size={18} />
              </button>
            </div>
            <div className="mentionModalContent">
              {!!selectedMention.brand_match_terms?.length && (
                <div className="mentionSignalRow">
                  {selectedMention.brand_match_terms.map((term) => (
                    <span className="mentionSignal" key={term}>{term}</span>
                  ))}
                </div>
              )}
              {!!mentionMetrics(selectedMention).length && (
                <div className="mentionMetricRow">
                  {mentionMetrics(selectedMention).map((item) => (
                    <span key={item}>{item}</span>
                  ))}
                </div>
              )}
              {mentionText(selectedMention)
                ? <p data-i18n-ignore="true">{mentionText(selectedMention)}</p>
                : <p>Bu mentionda matn topilmadi.</p>}
              {selectedMention.analysis && !selectedMention.analysis.error && (
                <div className="mentionAnalysis modalAnalysis">
                  <div className="mentionBadgeRow">
                    {selectedMention.analysis.sentiment && (
                      <span className={`sentimentBadge ${selectedMention.analysis.sentiment}`}>
                        {sentimentLabels[selectedMention.analysis.sentiment] || selectedMention.analysis.sentiment}
                      </span>
                    )}
                    {selectedMention.analysis.risk_level && (
                      <span className={`riskBadge ${selectedMention.analysis.risk_level}`}>
                        {riskLabels[selectedMention.analysis.risk_level] || selectedMention.analysis.risk_level}
                      </span>
                    )}
                  </div>
                  {selectedMention.analysis.summary && <p className="mentionSummary">{selectedMention.analysis.summary}</p>}
                  {selectedMention.analysis.suggested_action && <p className="mentionAction">{selectedMention.analysis.suggested_action}</p>}
                </div>
              )}
              {selectedMention.permalink && (
                <a className="button secondary modalLink" href={selectedMention.permalink} target="_blank" rel="noreferrer">
                  YouTube'da ochish
                </a>
              )}
            </div>
          </section>
        </div>
      )}
    </section>
  );
}

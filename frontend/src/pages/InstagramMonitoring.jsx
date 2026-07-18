import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  BarChart3,
  Check,
  Copy,
  Eye,
  EyeOff,
  HelpCircle,
  Heart,
  Instagram,
  KeyRound,
  Plus,
  RefreshCw,
  Send,
  Sparkles,
  Trash2,
  Webhook,
  MessageCircle,
} from "lucide-react";
import { clearApiCache, endpoints, readSelectedBrandId, resolveSelectedBrandId, saveSelectedBrandId } from "../api/client";
import { MonitoringInsights } from "../components/MonitoringInsights";
import { PageHeader } from "../components/PageHeader";
import { Sidebar } from "../components/Sidebar";
import { StatsBar } from "../components/StatsBar";
import { formatUiDate, translateUiText } from "../i18n";

const itemTypeLabels = {
  comment: "Comment",
  mention: "@Mention",
  caption: "Post",
  post: "Post",
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

function formatDate(value) {
  if (!value) return "";
  return formatUiDate(value, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

const emptyForm = {
  ig_user_id: "",
  access_token: "",
  username: "",
  brand_id: "",
  source_category: "owned",
  monitoring_mode: "all_messages",
};

export function InstagramMonitoring() {
  const [botStatus, setBotStatus] = useState(null);
  const [status, setStatus] = useState(null);
  const [brands, setBrands] = useState([]);
  const [sources, setSources] = useState([]);
  const [summary, setSummary] = useState(null);
  const [mentions, setMentions] = useState([]);
  const [selectedBrandId, setSelectedBrandId] = useState(() => readSelectedBrandId());
  const [form, setForm] = useState(emptyForm);
  const [demo, setDemo] = useState({ brand_id: "", author: "", text: "" });
  const [demoSubmitting, setDemoSubmitting] = useState(false);
  const [showToken, setShowToken] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [syncingSourceId, setSyncingSourceId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [copied, setCopied] = useState("");
  const brandRef = useRef("");
  const refreshTimer = useRef(null);

  useEffect(() => {
    brandRef.current = selectedBrandId;
  }, [selectedBrandId]);

  const visibleSources = useMemo(
    () => selectedBrandId ? sources.filter((source) => source.brand_id === selectedBrandId) : [],
    [sources, selectedBrandId],
  );

  const loadData = useCallback(async (brandId) => {
    const active = (brandId ?? brandRef.current) || "";
    try {
      const [sourcesData, summaryData, mentionsData] = await Promise.all([
        endpoints.instagramSources(),
        endpoints.instagramSummary(active),
        endpoints.instagramMentions(active),
      ]);
      setSources(sourcesData);
      setSummary(summaryData);
      setMentions(mentionsData);
      setError("");
    } catch (err) {
      setError(err.message || "Ma'lumotni yuklab bo'lmadi");
    }
  }, []);

  const loadInitial = useCallback(async () => {
    setLoading(true);
    try {
      const [brandsData, statusData, botData] = await Promise.all([
        endpoints.brands(),
        endpoints.instagramStatus(),
        endpoints.botStatus().catch(() => null),
      ]);
      setBrands(brandsData);
      setStatus(statusData);
      setBotStatus(botData);
      const activeBrandId = resolveSelectedBrandId(brandsData, brandRef.current);
      brandRef.current = activeBrandId;
      setSelectedBrandId(activeBrandId);
      setForm((current) => ({ ...current, brand_id: current.brand_id || activeBrandId }));
      await loadData(activeBrandId);
    } catch (err) {
      setError(err.message || "Yuklashda xatolik");
    } finally {
      setLoading(false);
    }
  }, [loadData]);

  useEffect(() => {
    loadInitial();
  }, [loadInitial]);

  useEffect(() => {
    loadData(selectedBrandId);
  }, [selectedBrandId, loadData]);

  // Realtime: reload (debounced) when an Instagram mention / analysis event arrives.
  useEffect(() => {
    const source = endpoints.eventsStream();
    const onEvent = (event) => {
      try {
        const data = JSON.parse(event.data || "{}");
        if (data.platform && data.platform !== "instagram") return;
      } catch {
        /* ignore */
      }
      clearTimeout(refreshTimer.current);
      refreshTimer.current = setTimeout(() => {
        clearApiCache("/instagram/");
        loadData(brandRef.current);
      }, 800);
    };
    source.addEventListener("instagram_mention", onEvent);
    source.addEventListener("analysis_updated", onEvent);
    source.onerror = () => {};
    return () => {
      clearTimeout(refreshTimer.current);
      source.close();
    };
  }, [loadData]);

  const statItems = useMemo(
    () => [
      { label: "Akkaunt", value: summary?.sources_total || 0, icon: Activity },
      { label: "Post", value: summary?.posts_total || 0, icon: BarChart3 },
      { label: "Comment", value: summary?.comments_total || 0, icon: MessageCircle },
      { label: "Like", value: summary?.likes_total || 0, icon: Heart },
    ],
    [summary],
  );

  const handleConnect = async (event) => {
    event.preventDefault();
    if (!form.brand_id) {
      setError("Brand tanlash majburiy.");
      return;
    }
    if (!form.access_token.trim()) {
      setError("Access token majburiy. Akkaunt token'dan avtomatik aniqlanadi.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const created = await endpoints.instagramConnect({
        access_token: form.access_token.trim(),
        username: form.username.trim().replace(/^@+/, "") || null,
        brand_id: form.brand_id || null,
        source_category: form.source_category,
        monitoring_mode: form.monitoring_mode,
      });
      setForm({ ...emptyForm, brand_id: form.brand_id });
      try {
        const synced = await endpoints.instagramSyncSource(created.id);
        setNotice(
          `Ulandi: @${created.username || created.ig_user_id}. ${synced.posts_created} post va ${synced.comments_created} comment olindi; ${synced.records_updated} yozuv yangilandi.`,
        );
      } catch (syncError) {
        setNotice(`Ulandi: @${created.username || created.ig_user_id}. Avtomatik poller ishga tushdi.`);
        setError(syncError.message || "Birinchi sinxronlash ishlamadi; token ruxsatlarini tekshiring.");
      }
      clearApiCache("/instagram/");
      await loadData(brandRef.current);
    } catch (err) {
      setError(err.message || "Ulashda xatolik");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDemo = async (event) => {
    event.preventDefault();
    const brandId = demo.brand_id || selectedBrandId || brands[0]?.id || "";
    if (!brandId) {
      setError("Avval brand tanlang (yoki Brendlar bo'limida brand yarating).");
      return;
    }
    const lines = demo.text.split("\n").map((s) => s.trim()).filter(Boolean);
    if (lines.length === 0) {
      setError("Kamida bitta komment matnini kiriting (har qatorda bitta komment).");
      return;
    }
    setDemoSubmitting(true);
    setError("");
    try {
      const comments = lines.map((text) => ({
        text,
        author_username: demo.author.trim() || null,
        item_type: "comment",
      }));
      const res = await endpoints.instagramManualIngest({ brand_id: brandId, comments });
      setNotice(`${res.created} ta komment AI tahlilga yuborildi. Natijalar bir necha soniyada pastda ko'rinadi.`);
      setDemo({ ...demo, text: "" });
      clearApiCache("/instagram/");
      await loadData(brandRef.current);
    } catch (err) {
      setError(err.message || "Demo yuborishda xatolik");
    } finally {
      setDemoSubmitting(false);
    }
  };

  const handleDelete = async (source) => {
    const name = source.username ? `@${source.username}` : source.account_name || source.ig_user_id;
    const confirmed = window.confirm(translateUiText(
      `“${name}” akkaunti butunlay o'chirilsinmi? Unga tegishli barcha post, comment, @mention va AI tahlillar ham o'chadi. Bu amalni ortga qaytarib bo'lmaydi.`,
    ));
    if (!confirmed) return;
    setError("");
    setNotice("");
    try {
      const deleted = await endpoints.instagramDeleteSource(source.id);
      setNotice(`${deleted.sources_deleted} ta akkaunt, ${deleted.mentions_deleted} ta post/comment va ${deleted.analyses_deleted} ta AI tahlil o'chirildi.`);
      clearApiCache("/instagram/");
      await loadData(brandRef.current);
    } catch (err) {
      setError(err.message || "O'chirishda xatolik");
    }
  };

  const handleValidate = async (sourceId) => {
    setError("");
    try {
      const s = await endpoints.instagramValidateSource(sourceId);
      setNotice(s.token_status === "active" ? `@${s.username} token faol` : `Token yaroqsiz: ${s.status_detail || ""}`);
      clearApiCache("/instagram/");
      await loadData(brandRef.current);
    } catch (err) {
      setError(err.message || "Tekshirishda xatolik");
    }
  };

  const handleSync = async (sourceId) => {
    setSyncingSourceId(sourceId);
    setError("");
    try {
      const synced = await endpoints.instagramSyncSource(sourceId);
      clearApiCache("/instagram/");
      setNotice(
        `Sync tugadi: ${synced.media_seen} post tekshirildi, ${synced.posts_created} post va ${synced.comments_created} comment qo'shildi, ${synced.records_updated} ta engagement yangilandi.`,
      );
      await loadData(brandRef.current);
    } catch (err) {
      setError(err.message || "Instagram sinxronlashda xatolik");
    } finally {
      setSyncingSourceId("");
    }
  };

  const handleSwapToken = async (sourceId) => {
    const token = window.prompt(translateUiText("Yangi access token'ni joylang (akkaunt token'dan aniqlanadi):"));
    if (!token || !token.trim()) return;
    setError("");
    try {
      const s = await endpoints.instagramUpdateSource(sourceId, { access_token: token.trim() });
      if (s.token_status === "active") {
        const synced = await endpoints.instagramSyncSource(sourceId);
        setNotice(
          `Token yangilandi: @${s.username}. ${synced.media_seen} post tekshirildi va ${synced.comments_created} comment qo'shildi.`,
        );
      } else {
        setNotice(`Yangi token yaroqsiz: ${s.status_detail || ""}`);
      }
      clearApiCache("/instagram/");
      await loadData(brandRef.current);
    } catch (err) {
      setError(err.message || "Token yangilashda xatolik");
    }
  };

  const copy = (label, value) => {
    navigator.clipboard?.writeText(value);
    setCopied(label);
    setTimeout(() => setCopied(""), 1500);
  };

  return (
    <div className="appShell">
      <Sidebar botStatus={botStatus} activePath="/instagram-monitoring" />
      <main className="main">
        <PageHeader
          eyebrow="Instagram source catalog"
          title="Instagram monitoring"
          loading={loading}
        />

        {error && <div className="errorBanner">{error}</div>}
        {notice && <div className="loadingBar">{notice}</div>}
        {status && !status.configured && (
          <div className="loadingBar">
            Polling orqali post/comment yig'ish tayyor. Haqiqiy webhook uchun serverda <code>IG_APP_ID</code> va <code>IG_APP_SECRET</code> hali sozlanmagan.
          </div>
        )}

        <StatsBar items={statItems} loading={loading} />
        {summary && summary.post_comments_total > summary.comments_total && (
          <div className="loadingBar">
            Instagram post hisoblagichi {summary.post_comments_total} ta comment borligini ko'rsatmoqda; hozircha {summary.comments_total} ta comment matni import qilingan.
            {visibleSources.some((source) => source.token_status === "invalid")
              ? " Token yaroqsiz bo'lib qolgan — “Token yangilash” orqali yangi token kiriting; sync avtomatik boshlanadi."
              : " Ulangan akkauntdagi “Sync” tugmasi comment matnlarini qayta yuklaydi."}
          </div>
        )}
        <MonitoringInsights platform="instagram" sources={visibleSources} summary={summary} status={status} loading={loading} />

        <section className="monitoringWorkspace">
          <section className="recentSection">
            <div className="sectionHeader">
              <div>
                <span className="eyebrow">Instagram API</span>
                <h2>Yangi akkaunt ulash</h2>
              </div>
            </div>

            <div className="connectedAccountsPanel">
              <div className="connectedAccountsHead">
                <div>
                  <span className="eyebrow">Ulangan akkauntlar</span>
                  <h3>Instagram Business</h3>
                </div>
                <span className="accountCountBadge">{visibleSources.length}</span>
              </div>

              <div className="sourceList">
                {visibleSources.length === 0 && (
                  <div className="emptyState connectedAccountsEmpty">
                    <Instagram size={22} />
                    <strong>Hali akkaunt ulanmagan</strong>
                    <span>Username, token va brandni kiriting, so‘ng “Akkauntni ulash” tugmasini bosing.</span>
                  </div>
                )}
                {visibleSources.map((source) => (
                  <div className="igAccountRow" key={source.id}>
                    <div className="sourceIcon"><Instagram size={18} /></div>
                    <div className="sourceBody">
                      <strong>
                        @{source.username || source.ig_user_id}{" "}
                        <span className={`tokenBadge ${source.token_status}`}>
                          {source.token_status === "active"
                            ? "faol"
                            : source.token_status === "invalid"
                            ? "yaroqsiz"
                            : "?"}
                        </span>
                      </strong>
                      <span className="sourceMeta">
                        {source.monitoring_mode === "all_messages" ? "Barcha kommentlar" : "Faqat mos"} ·{" "}
                        {source.webhook_subscribed ? "webhook ✓" : "poller (60s)"}
                        {source.token_status === "invalid" && source.status_detail
                          ? ` · ${source.status_detail.slice(0, 40)}`
                          : ""}
                      </span>
                    </div>
                    <div className="accountActionGroup">
                      <button className="accountActionButton" type="button" onClick={() => handleValidate(source.id)}>
                        <RefreshCw size={14} />
                        <span>Tekshirish</span>
                      </button>
                      <button
                        className="accountActionButton"
                        type="button"
                        disabled={syncingSourceId === source.id}
                        onClick={() => handleSync(source.id)}
                      >
                        <Activity className={syncingSourceId === source.id ? "spin" : ""} size={14} />
                        <span>{syncingSourceId === source.id ? "Yangilanmoqda" : "Sync"}</span>
                      </button>
                      <button className="accountActionButton" type="button" onClick={() => handleSwapToken(source.id)}>
                        <KeyRound size={14} />
                        <span>Token yangilash</span>
                      </button>
                      <button className="accountActionButton danger" type="button" onClick={() => handleDelete(source)}>
                        <Trash2 size={14} />
                        <span>O‘chirish</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <form className="loginForm" onSubmit={handleConnect} style={{ marginBottom: 18 }}>
              <label className="field">
                <span>Instagram username (ixtiyoriy)</span>
                <input
                  className="input"
                  value={form.username}
                  onChange={(e) => setForm({ ...form, username: e.target.value })}
                  autoComplete="off"
                />
                <small>Masalan, <strong>brand_nomi</strong>. Token to'g'ri bo'lsa profil avtomatik aniqlanadi.</small>
              </label>
              <label className="field">
                <span>Access token</span>
                <div className="tokenInputWrap">
                  <input
                    className="input"
                    type={showToken ? "text" : "password"}
                    value={form.access_token}
                    onChange={(e) => setForm({ ...form, access_token: e.target.value })}
                    autoComplete="off"
                  />
                  <button
                    type="button"
                    className="eyeBtn"
                    onClick={() => setShowToken((v) => !v)}
                    title={showToken ? "Yashirish" : "Ko'rsatish"}
                  >
                    {showToken ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                <small>Meta bergan tokenni kiriting. Token brauzer tarixiga yoki loglarga chiqarilmaydi.</small>
              </label>
              <label className="field">
                <span>Brand</span>
                <select
                  className="input select"
                  value={form.brand_id}
                  onChange={(e) => {
                    const brandId = saveSelectedBrandId(e.target.value);
                    brandRef.current = brandId;
                    setSelectedBrandId(brandId);
                    setForm({ ...form, brand_id: brandId });
                  }}
                  required
                >
                  <option value="">{translateUiText("Brand tanlang")}</option>
                  {brands.map((b) => (
                    <option key={b.id} value={b.id}>{b.name}</option>
                  ))}
                </select>
              </label>
              <button className="button primary fullButton" type="submit" disabled={submitting}>
                <Plus size={17} />
                <span>{submitting ? "Ulanmoqda..." : "Akkauntni ulash"}</span>
              </button>
            </form>

            <div className="igGuide">
              <div className="igGuideHead">
                <HelpCircle size={15} />
                <strong>
                  {form.username.trim()
                    ? `@${form.username.trim()} profili tokenini olish`
                    : "Bu profil tokenini qayerdan olaman?"}
                </strong>
              </div>
              <div className="igGuideBody">
                <p className="igGuideNote">
                  Joriy <strong>Instagram Login</strong> tokeni Facebook Page'siz ham ishlayapti. Agar Facebook Login yo'lidan foydalanmoqchi bo'lsangiz,
                  Instagram va qolgan yagona Facebook Page bir-biriga bog'lanishi kerak. Blok muddati tugamaguncha qayta-qayta urinmang.
                </p>
                <ol>
                  <li>
                    Instagram <strong>@{form.username.trim() || "brand_profili"}</strong> profilini <strong>Business yoki Creator</strong> qiling.
                  </li>
                  <li>
                    Facebook'da kerakli Page'ga switch qiling → <strong>Settings & privacy → Settings → Permissions → Linked accounts → Instagram → Connect account</strong>.
                    Facebook useringiz shu Page uchun Full control yoki kerakli task access'ga ega bo'lsin.
                  </li>
                  <li>
                    Meta Developer App'da <strong>Facebook Login</strong> va <strong>Instagram Graph API</strong> mahsulotlarini yoqing.
                    Development mode'da Facebook user va Instagram profilni App Roles/Testers'ga qo'shing.
                  </li>
                  <li>
                    Graph API Explorer yoki o'z Facebook Login oqimingizdan User token yarating. Ruxsatlar:
                    {" "}<code>instagram_basic</code>, <code>instagram_manage_comments</code>,
                    {" "}<code>pages_show_list</code>, <code>pages_read_engagement</code>.
                  </li>
                  <li>
                    Tokenni nusxalab yuqoridagi <strong>Access token</strong> ga joylang → <strong>Akkauntni ulash</strong>.
                    Profil avtomatik aniqlanadi.
                  </li>
                </ol>
                <p className="igGuideNote">
                  “Something went wrong” yana chiqsa yangi Page yaratmang: Page access, professional account va Instagram'da boshqa Page ulanmaganini tekshiring,
                  Facebook/Instagram ilovalaridan qayta login qiling va bitta urinish qiling.
                </p>
              </div>
            </div>

            <form className="demoCard" onSubmit={handleDemo}>
              <div className="panelHeader">
                <div>
                  <span className="eyebrow"><Sparkles size={13} /> Meta'siz sinov</span>
                  <h3>Demo AI tahlil</h3>
                </div>
              </div>
              <p className="demoHint">
                Token yo'q bo'lsa ham tizimni hoziroq sinang: kommentlarni joylang. AI real-time'da
                sentiment, risk va tavsiya beradi. Har qatorda bitta komment.
              </p>
              <label className="field">
                <span>Brand</span>
                <select
                  className="input select"
                  value={demo.brand_id || selectedBrandId || ""}
                  onChange={(e) => setDemo({ ...demo, brand_id: e.target.value })}
                >
                  <option value="">{translateUiText("Brand tanlang")}</option>
                  {brands.map((b) => (
                    <option key={b.id} value={b.id}>{b.name}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Muallif (ixtiyoriy)</span>
                <input
                  className="input"
                  value={demo.author}
                  onChange={(e) => setDemo({ ...demo, author: e.target.value })}
                  autoComplete="off"
                />
              </label>
              <label className="field">
                <span>Kommentlar (har qatorda bittadan)</span>
                <textarea
                  className="input demoTextarea"
                  value={demo.text}
                  onChange={(e) => setDemo({ ...demo, text: e.target.value })}
                  rows={4}
                />
              </label>
              <button className="button primary fullButton" type="submit" disabled={demoSubmitting}>
                <Send size={16} />
                <span>{demoSubmitting ? "Tahlilga yuborilmoqda..." : "AI tahlilga yuborish"}</span>
              </button>
            </form>

            {status && (
              <details className="igGuide">
                <summary>
                  <Webhook size={15} />
                  <span>Qo'shimcha (ixtiyoriy): tezkor webhook</span>
                </summary>
                <div className="webhookCard webhookCardInner">
                  <p className="webhookHint">
                    Kommentlar hozir har <strong>60 soniyada</strong> avtomatik yig'iladi. Bir zumda (millisekundda)
                    olish uchun ixtiyoriy Meta webhook: Meta App → Instagram → Webhooks:
                  </p>
                  <div className="webhookRow">
                    <span>Callback URL</span>
                    <code>{status.webhook_callback_url}</code>
                    <button className="iconButton" type="button" onClick={() => copy("url", status.webhook_callback_url)}>
                      {copied === "url" ? <Check size={14} /> : <Copy size={14} />}
                    </button>
                  </div>
                  <div className="webhookRow">
                    <span>Verify token</span>
                    <code>{status.verify_token_set ? "IG_VERIFY_TOKEN (.env)" : "sozlanmagan"}</code>
                  </div>
                  <p className="webhookHint">
                    So'ng <strong>comments</strong> va <strong>live_comments</strong> fieldlariga obuna bo'ling.
                  </p>
                </div>
              </details>
            )}
          </section>

          <section className="recentSection">
            <div className="sectionHeader">
              <div>
                <span className="eyebrow">Oxirgi mentionlar</span>
                <h2>Instagram comment va @mention oqimi</h2>
              </div>
            </div>
            <div className="mentionList">
              {mentions.length === 0 && <div className="emptyState">Mention yo'q</div>}
              {mentions.map((mention) => (
                <a
                  className="mentionItem"
                  key={mention.id}
                  href={mention.permalink || "#"}
                  target="_blank"
                  rel="noreferrer"
                >
                  <div className="mentionIcon"><Instagram size={16} /></div>
                  <div className="mentionBody">
                    {mention.text
                      ? <p data-i18n-ignore="true">{mention.text}</p>
                      : <p>(matnsiz)</p>}
                    <div className="mentionMetricRow">
                      <span>@{mention.author_username || "aniqlanmagan"}</span>
                      <span className="mentionSignal">{itemTypeLabels[mention.item_type] || mention.item_type}</span>
                      {!!mention.brand_match_terms?.length && <span className="mentionSignal">Brand signal</span>}
                      {typeof mention.like_count === "number" && (
                        <span className="mentionSignal"><Heart size={12} /> {mention.like_count}</span>
                      )}
                      {typeof mention.comment_count === "number" && (
                        <span className="mentionSignal"><MessageCircle size={12} /> {mention.comment_count}</span>
                      )}
                    </div>
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
                        {mention.analysis.suggested_action && (
                          <p className="mentionAction">{mention.analysis.suggested_action}</p>
                        )}
                      </div>
                    ) : (
                      <span className="mentionPending">AI tahlil kutilmoqda…</span>
                    )}
                  </div>
                  <span className="mentionMeta">{formatDate(mention.created_at)}</span>
                </a>
              ))}
            </div>
          </section>
        </section>
      </main>
    </div>
  );
}

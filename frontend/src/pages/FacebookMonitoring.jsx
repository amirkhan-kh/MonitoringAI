import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  BarChart3,
  Brain,
  Check,
  Copy,
  Eye,
  EyeOff,
  Facebook,
  HelpCircle,
  KeyRound,
  Plus,
  RefreshCw,
  Send,
  ShieldAlert,
  Sparkles,
  Trash2,
  Webhook,
} from "lucide-react";
import { clearApiCache, endpoints, readSelectedBrandId, resolveSelectedBrandId, saveSelectedBrandId } from "../api/client";
import DeleteSourceModal from "../components/DeleteSourceModal";
import { MonitoringInsights } from "../components/MonitoringInsights";
import { MentionsAnalysisPanels } from "../components/RecentMentions";
import { PageHeader } from "../components/PageHeader";
import { Sidebar } from "../components/Sidebar";
import { StatsBar } from "../components/StatsBar";
import { formatUiDate, translateUiText } from "../i18n";

const itemTypeLabels = {
  comment: "Comment",
  reply: "Reply",
  post: "Post",
  mention: "@Mention",
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
  page_name: "",
  access_token: "",
  brand_id: "",
  source_category: "owned",
  monitoring_mode: "all_messages",
};

export function FacebookMonitoring() {
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
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
        endpoints.facebookSources(),
        endpoints.facebookSummary(active),
        endpoints.facebookMentions(active),
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
        endpoints.facebookStatus(),
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

  useEffect(() => {
    const source = endpoints.eventsStream();
    const onEvent = (event) => {
      try {
        const data = JSON.parse(event.data || "{}");
        if (data.platform && data.platform !== "facebook") return;
      } catch {
        /* ignore */
      }
      clearTimeout(refreshTimer.current);
      refreshTimer.current = setTimeout(() => {
        clearApiCache("/facebook/");
        loadData(brandRef.current);
      }, 800);
    };
    source.addEventListener("facebook_mention", onEvent);
    source.addEventListener("analysis_updated", onEvent);
    source.onerror = () => {};
    return () => {
      clearTimeout(refreshTimer.current);
      source.close();
    };
  }, [loadData]);

  const statItems = useMemo(
    () => [
      { label: "Sahifa", value: summary?.sources_total || 0, icon: Activity },
      { label: "Comment", value: summary?.mentions_total || 0, icon: BarChart3 },
      { label: "AI tahlil", value: summary?.analyzed_total || 0, icon: Brain },
      { label: "High risk", value: summary?.high_risk || 0, icon: ShieldAlert, tone: "risk" },
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
      setError("Access token majburiy. Sahifa token'dan avtomatik aniqlanadi.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const created = await endpoints.facebookConnect({
        access_token: form.access_token.trim(),
        page_name: form.page_name.trim() || null,
        brand_id: form.brand_id || null,
        source_category: form.source_category,
        monitoring_mode: form.monitoring_mode,
      });
      setForm({ ...emptyForm, brand_id: form.brand_id });
      setNotice(`Ulandi: ${created.page_name || created.page_id}. Kommentlar yig'ila boshlaydi.`);
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
        author_name: demo.author.trim() || null,
        item_type: "comment",
      }));
      const res = await endpoints.facebookManualIngest({ brand_id: brandId, comments });
      setNotice(`${res.created} ta komment AI tahlilga yuborildi. Natijalar bir necha soniyada pastda ko'rinadi.`);
      setDemo({ ...demo, text: "" });
      await loadData(brandRef.current);
    } catch (err) {
      setError(err.message || "Demo yuborishda xatolik");
    } finally {
      setDemoSubmitting(false);
    }
  };

  const handleDelete = (source) => {
    setPendingDelete(source);
  };

  const confirmDelete = async (purgeMentions) => {
    const source = pendingDelete;
    if (!source) return;
    setError("");
    setNotice("");
    setDeleteBusy(true);
    try {
      const deleted = await endpoints.facebookDeleteSource(source.id, purgeMentions);
      setNotice(
        purgeMentions
          ? `${deleted.sources_deleted} ta sahifa, ${deleted.mentions_deleted} ta post/comment va ${deleted.analyses_deleted} ta AI tahlil o'chirildi.`
          : `${deleted.sources_deleted} ta sahifa o'chirildi. ${deleted.mentions_retained} ta tahlil qilingan mention saqlandi — bu sahifani qayta ulasangiz ular qayta tahlil qilinmaydi.`,
      );
      setPendingDelete(null);
      await loadData(brandRef.current);
    } catch (err) {
      setError(err.message || "O'chirishda xatolik");
    } finally {
      setDeleteBusy(false);
    }
  };

  const handleValidate = async (sourceId) => {
    setError("");
    try {
      const s = await endpoints.facebookValidateSource(sourceId);
      setNotice(s.token_status === "active" ? `${s.page_name} token faol` : `Token yaroqsiz: ${s.status_detail || ""}`);
      await loadData(brandRef.current);
    } catch (err) {
      setError(err.message || "Tekshirishda xatolik");
    }
  };

  const handleSwapToken = async (sourceId) => {
    const token = window.prompt(translateUiText("Yangi access token'ni joylang (sahifa token'dan aniqlanadi):"));
    if (!token || !token.trim()) return;
    setError("");
    try {
      const s = await endpoints.facebookUpdateSource(sourceId, { access_token: token.trim() });
      setNotice(s.token_status === "active" ? `Token yangilandi: ${s.page_name}` : `Yangi token yaroqsiz: ${s.status_detail || ""}`);
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
      <Sidebar botStatus={botStatus} activePath="/facebook-monitoring" />
      <main className="main">
        <PageHeader
          eyebrow="Facebook source catalog"
          title="Facebook monitoring"
          loading={loading}
        />

        {error && <div className="errorBanner">{error}</div>}
        {notice && <div className="loadingBar">{notice}</div>}

        <StatsBar items={statItems} loading={loading} />
        <MonitoringInsights platform="facebook" sources={visibleSources} summary={summary} status={status} loading={loading} />

        <section className="monitoringWorkspace">
          <section className="recentSection">
            <div className="sectionHeader">
              <div>
                <span className="eyebrow">Ulangan sahifalar</span>
                <h2>Facebook Page</h2>
              </div>
            </div>

            <form className="loginForm" onSubmit={handleConnect} style={{ marginBottom: 18 }}>
              <label className="field">
                <span>Facebook Page nomi</span>
                <input
                  className="input"
                  value={form.page_name}
                  onChange={(e) => setForm({ ...form, page_name: e.target.value })}
                  autoComplete="off"
                />
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
                <span>{submitting ? "Ulanmoqda..." : "Sahifani ulash"}</span>
              </button>
            </form>

            <div className="igGuide">
              <div className="igGuideHead">
                <HelpCircle size={15} />
                <strong>
                  {form.page_name.trim()
                    ? `"${form.page_name.trim()}" sahifasi tokenini olish`
                    : "Bu sahifa tokenini qayerdan olaman?"}
                </strong>
              </div>
              <div className="igGuideBody">
                <p className="igGuideNote">
                  O'z <strong>ishonchli Meta Business</strong> akkauntingizdan Page token olinadi. Own/test sahifada sinab ko'rish mumkin,
                  lekin keng production comment oqimi uchun Meta permission/App Review talab qilinishi mumkin.
                </p>
                <ol>
                  <li>
                    <a href="https://business.facebook.com/settings" target="_blank" rel="noreferrer">business.facebook.com/settings</a>
                    {" "}→ chapdan <strong>Users → System users</strong> → <strong>Add</strong> (yangi system user).
                  </li>
                  <li>System user → <strong>Assign assets</strong> → Facebook Page'ni tanlang (Full control).</li>
                  <li>
                    <strong>Generate new token</strong> → App'ni tanlang → ruxsatlar:
                    {" "}<code>pages_show_list</code>, <code>pages_read_engagement</code>,
                    {" "}<code>pages_read_user_content</code>, <code>pages_manage_metadata</code>.
                  </li>
                  <li>
                    Tokenni nusxalab yuqoridagi <strong>Access token</strong> ga joylang → <strong>Sahifani ulash</strong>.
                    Sahifa avtomatik aniqlanadi.
                  </li>
                </ol>
                <p className="igGuideNote">
                  Token hali yo'qmi? Pastdagi <strong>Demo AI tahlil</strong> orqali tizimni hoziroq sinab ko'ring.
                </p>
              </div>
            </div>

            <div className="sourceList">
              {visibleSources.length === 0 && <div className="emptyState">Hali sahifa ulanmagan</div>}
              {visibleSources.map((source) => (
                <div className="igAccountRow" key={source.id}>
                  <div className="sourceIcon"><Facebook size={18} /></div>
                  <div className="sourceBody">
                    <strong>
                      {source.page_name || source.page_id}{" "}
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
                  <button className="iconButton" type="button" title="Tekshirish" onClick={() => handleValidate(source.id)}>
                    <RefreshCw size={15} />
                  </button>
                  <button className="iconButton" type="button" title="Token yangilash" onClick={() => handleSwapToken(source.id)}>
                    <KeyRound size={15} />
                  </button>
                  <button className="iconButton danger" type="button" title="Sahifa va unga tegishli barcha ma'lumotlarni o'chirish" onClick={() => handleDelete(source)}>
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
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
                    Kommentlar hozir har <strong>60 soniyada</strong> avtomatik yig'iladi. Bir zumda olish uchun
                    ixtiyoriy Meta webhook: Meta App → Webhooks → Page:
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
                    <code>{status.verify_token_set ? "FB_VERIFY_TOKEN (.env)" : "sozlanmagan"}</code>
                  </div>
                  <p className="webhookHint">
                    So'ng <strong>feed</strong> fieldiga obuna bo'ling.
                  </p>
                </div>
              </details>
            )}
          </section>

          <section className="recentSection">
            <div className="sectionHeader">
              <div>
                <span className="eyebrow">Oxirgi kommentlar</span>
                <h2>Facebook comment oqimi</h2>
              </div>
            </div>
            <div className="mentionList">
              {mentions.length === 0 && <div className="emptyState">Comment yo'q</div>}
              {mentions.map((mention) => (
                <a
                  className="mentionItem"
                  key={mention.id}
                  href={mention.permalink || "#"}
                  target="_blank"
                  rel="noreferrer"
                >
                  <div className="mentionIcon"><Facebook size={16} /></div>
                  <div className="mentionBody">
                    {mention.text
                      ? <p data-i18n-ignore="true">{mention.text}</p>
                      : <p>(matnsiz)</p>}
                    <div className="mentionMetricRow">
                      <span>{mention.author_name || "aniqlanmagan"}</span>
                      <span className="mentionSignal">{itemTypeLabels[mention.item_type] || mention.item_type}</span>
                      {!!mention.brand_match_terms?.length && <span className="mentionSignal">Brand signal</span>}
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

        <MentionsAnalysisPanels
          mentions={mentions}
          loading={loading}
          platformLabel="Facebook"
        />

        <DeleteSourceModal
          open={Boolean(pendingDelete)}
          sourceName={pendingDelete ? pendingDelete.page_name || pendingDelete.username || pendingDelete.page_id : ""}
          busy={deleteBusy}
          onCancel={() => setPendingDelete(null)}
          onConfirm={confirmDelete}
        />
      </main>
    </div>
  );
}

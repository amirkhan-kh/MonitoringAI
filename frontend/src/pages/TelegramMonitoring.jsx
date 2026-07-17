import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { X } from "lucide-react";
import { clearApiCache, endpoints, readSelectedBrandId, resolveSelectedBrandId } from "../api/client";
import { MonitoringInsights } from "../components/MonitoringInsights";
import { PageHeader } from "../components/PageHeader";
import { RecentMentions } from "../components/RecentMentions";
import { Sidebar } from "../components/Sidebar";
import { SourceBoard } from "../components/SourceBoard";
import { SourceForm } from "../components/SourceForm";
import { StatsBar } from "../components/StatsBar";
import { translateUiText } from "../i18n";

export function TelegramMonitoring() {
  const [botStatus, setBotStatus] = useState(null);
  const [brands, setBrands] = useState([]);
  const [categories, setCategories] = useState([]);
  const [sources, setSources] = useState([]);
  const [summary, setSummary] = useState(null);
  const [mentions, setMentions] = useState([]);
  const [selectedBrandId, setSelectedBrandId] = useState(() => readSelectedBrandId());
  const [accessResult, setAccessResult] = useState(null);
  const [sourceResult, setSourceResult] = useState(null);
  const [selectedCategoryKey, setSelectedCategoryKey] = useState("owned");
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
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

  // Stable identity (no deps) so it never re-triggers the SSE effect below.
  const loadDashboard = useCallback(async (brandId) => {
    const activeBrandId = (brandId ?? selectedBrandIdRef.current) || "";
    lastLoadedBrandId.current = activeBrandId;
    const [sourceRows, summaryRow, mentionRows] = await Promise.all([
      endpoints.sources(),
      endpoints.dashboardSummary(activeBrandId),
      endpoints.mentions(activeBrandId),
    ]);
    setSources(sourceRows);
    setSummary(summaryRow);
    setMentions(mentionRows);
  }, []);

  const loadInitial = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [bot, categoryRows, brandRows] = await Promise.all([
        endpoints.botStatus(),
        endpoints.sourceCategories(),
        endpoints.brands(),
      ]);
      setBotStatus(bot);
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
        clearApiCache(["/telegram/", "/dashboard/summary", "/mentions"]);
        loadDashboard(selectedBrandIdRef.current).catch((err) => setError(err.message));
      }, 800);
    }

    eventSource.addEventListener("telegram_mention", scheduleRefresh);
    eventSource.addEventListener("analysis_updated", scheduleRefresh);
    eventSource.addEventListener("telegram_source", scheduleRefresh);

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

  async function handleAccessCheck(ref) {
    if (!ref?.trim()) return;
    const result = await endpoints.sourceAccessCheck(ref.trim());
    setAccessResult(result);
    setSourceResult({ type: "check", access: result });
  }

  async function handleImport(payload) {
    const result = await endpoints.importSources(payload);
    const importedSources = result.map((row) => row.source).filter((source) => source?.id);
    let latestSourceResult = null;
    for (const source of importedSources) {
      let refresh = null;
      let refreshError = "";
      try {
        refresh = await endpoints.refreshSource(source.id);
      } catch (err) {
        refreshError = err.message;
      }

      let backfill = null;
      try {
        backfill = await endpoints.backfillSource(source.id, { comments_per_post: 50 });
      } catch (err) {
        backfill = { ok: false, error: err.message, posts_seen: 0, comments_seen: 0 };
      }

      latestSourceResult = {
        type: "import",
        source: refresh?.source || source,
        access: refresh?.access,
        backfill,
        error: refreshError,
      };
    }
    if (latestSourceResult) setSourceResult(latestSourceResult);
    await loadDashboard(selectedBrandId);
  }

  async function handleToggleSource(source) {
    await endpoints.updateSource(source.id, { active: !source.active });
    await loadDashboard(selectedBrandId);
  }

  async function handleRefreshSource(source) {
    const result = await endpoints.refreshSource(source.id);
    setSourceResult({ type: "refresh", ...result });
    await loadDashboard(selectedBrandId);
  }

  async function handleBackfillSource(source) {
    let refresh = null;
    try {
      refresh = await endpoints.refreshSource(source.id);
    } catch (err) {
      refresh = { error: err.message };
    }
    const result = await endpoints.backfillSource(source.id, { comments_per_post: 50 });
    setSourceResult({ type: "backfill", source: refresh?.source || source, access: refresh?.access, backfill: result });
    await loadDashboard(selectedBrandId);
  }

  async function handleDeleteSource(source) {
    const name = source.title || (source.username ? `@${source.username}` : source.chat_id) || "Telegram source";
    const confirmed = window.confirm(translateUiText(
      `“${name}” source butunlay o'chirilsinmi? Unga tegishli barcha post, comment, AI tahlil va alertlar ham o'chadi. Bu amalni ortga qaytarib bo'lmaydi.`,
    ));
    if (!confirmed) return;
    setError("");
    setNotice("");
    try {
      const deleted = await endpoints.deleteSource(source.id);
      setNotice(`${deleted.sources_deleted} ta source, ${deleted.mentions_deleted} ta post/comment va ${deleted.analyses_deleted} ta AI tahlil o'chirildi.`);
      await loadDashboard(selectedBrandId);
    } catch (err) {
      setError(err.message || "Source o'chirishda xatolik yuz berdi.");
    }
  }

  const isInitialLoading = loading && !summary && !sources.length && !mentions.length;

  return (
    <div className="appShell">
      <Sidebar botStatus={botStatus} />
      <main className="main">
        <PageHeader
          loading={isInitialLoading}
        />

        {error && <div className="errorBanner">{error}</div>}
        {notice && <div className="loadingBar success">{notice}</div>}

        <StatsBar sources={visibleSources} summary={summary} loading={isInitialLoading} />
        <MonitoringInsights platform="telegram" sources={visibleSources} summary={summary} loading={isInitialLoading} />

        <section className="monitoringWorkspace">
          <SourceBoard
            categories={categories}
            sources={visibleSources}
            selectedCategoryKey={selectedCategoryKey}
            onCategoryChange={setSelectedCategoryKey}
            onOpenAdd={() => setIsAddModalOpen(true)}
            onToggleSource={handleToggleSource}
            onCheckSource={handleAccessCheck}
            onRefreshSource={handleRefreshSource}
            onBackfillSource={handleBackfillSource}
            onDeleteSource={handleDeleteSource}
            loading={isInitialLoading}
          />

          <RecentMentions mentions={mentions} loading={isInitialLoading} />
        </section>

        {isAddModalOpen && (
          <div className="modalOverlay" role="presentation" onMouseDown={() => setIsAddModalOpen(false)}>
            <section
              className="modalPanel"
              role="dialog"
              aria-modal="true"
              aria-labelledby="add-source-title"
              onMouseDown={(event) => event.stopPropagation()}
            >
              <div className="modalHeader">
                <div>
                  <h2 id="add-source-title">Manzil qo'shish</h2>
                  <p>Telegram kanal, group, bot yoki CSV/TXT ro'yxatini qo'shing.</p>
                </div>
                <button className="iconButton" type="button" aria-label="Yopish" onClick={() => setIsAddModalOpen(false)}>
                  <X size={18} />
                </button>
              </div>
              <div className="modalContent">
                <SourceForm
                  categories={categories}
                  selectedBrandId={selectedBrandId}
                  initialCategory={selectedCategoryKey}
                  onAccessCheck={handleAccessCheck}
                  onImport={handleImport}
                  accessResult={accessResult}
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

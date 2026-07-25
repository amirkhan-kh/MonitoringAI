import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link2, X } from "lucide-react";
import {
  clearApiCache,
  endpoints,
  readSelectedBrandId,
  resolveSelectedBrandId,
  saveSelectedBrandId,
} from "../api/client";
import DeleteSourceModal from "../components/DeleteSourceModal";
import { MonitoringInsights } from "../components/MonitoringInsights";
import { PageHeader } from "../components/PageHeader";
import { MentionsAnalysisPanels, RecentMentions } from "../components/RecentMentions";
import { Sidebar } from "../components/Sidebar";
import { SmartSelect } from "../components/SmartSelect";
import { SourceBoard } from "../components/SourceBoard";
import { StatsBar } from "../components/StatsBar";
import { TelegramConnectionForm } from "../components/TelegramConnectionForm";

export function TelegramMonitoring() {
  const [botStatus, setBotStatus] = useState(null);
  const [brands, setBrands] = useState([]);
  const [categories, setCategories] = useState([]);
  const [sources, setSources] = useState([]);
  const [summary, setSummary] = useState(null);
  const [mentions, setMentions] = useState([]);
  const [selectedBrandId, setSelectedBrandId] = useState(() => readSelectedBrandId());
  const [connection, setConnection] = useState(null);
  const [setupResult, setSetupResult] = useState(null);
  const [selectedCategoryKey, setSelectedCategoryKey] = useState("owned");
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [connectionLoading, setConnectionLoading] = useState(false);
  const [setupSaving, setSetupSaving] = useState(false);
  const [connectionDeleting, setConnectionDeleting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const realtimeRefreshTimer = useRef(null);
  const selectedBrandIdRef = useRef("");
  const lastLoadedBrandId = useRef("");
  const lastLoadedConnectionBrandId = useRef("");

  useEffect(() => {
    selectedBrandIdRef.current = selectedBrandId;
  }, [selectedBrandId]);

  const visibleSources = useMemo(() => {
    if (!selectedBrandId) return [];
    return sources.filter((source) => source.brand_id === selectedBrandId);
  }, [sources, selectedBrandId]);

  // Stable identity (no deps) so it never re-triggers the SSE effect below.
  const loadDashboard = useCallback(async (brandId) => {
    const activeBrandId = (brandId ?? selectedBrandIdRef.current) || "";
    lastLoadedBrandId.current = activeBrandId;
    if (!activeBrandId) {
      setSources([]);
      setSummary(null);
      setMentions([]);
      return;
    }
    const [sourceRows, summaryRow, mentionRows] = await Promise.all([
      endpoints.sources(),
      endpoints.dashboardSummary(activeBrandId),
      endpoints.mentions(activeBrandId),
    ]);
    setSources(sourceRows);
    setSummary(summaryRow);
    setMentions(mentionRows);
  }, []);

  const loadConnection = useCallback(async (brandId) => {
    const activeBrandId = (brandId ?? selectedBrandIdRef.current) || "";
    if (!activeBrandId) {
      lastLoadedConnectionBrandId.current = "";
      setConnection(null);
      return null;
    }
    setConnectionLoading(true);
    try {
      const row = await endpoints.telegramConnection(activeBrandId);
      lastLoadedConnectionBrandId.current = activeBrandId;
      setConnection(row);
      return row;
    } finally {
      setConnectionLoading(false);
    }
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
      selectedBrandIdRef.current = defaultBrandId;
      if (defaultBrandId && defaultBrandId !== selectedBrandId) {
        setSelectedBrandId(defaultBrandId);
      }
      await Promise.all([loadDashboard(defaultBrandId), loadConnection(defaultBrandId)]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [loadConnection, loadDashboard, selectedBrandId]);

  useEffect(() => {
    loadInitial();
  }, []);

  useEffect(() => {
    if (loading) return;
    const requests = [];
    if (selectedBrandId !== lastLoadedBrandId.current) requests.push(loadDashboard(selectedBrandId));
    if (selectedBrandId !== lastLoadedConnectionBrandId.current) requests.push(loadConnection(selectedBrandId));
    if (!requests.length) return;
    Promise.all(requests).catch((err) => setError(err.message));
  }, [loading, selectedBrandId, loadConnection, loadDashboard]);

  // Open the realtime stream once for the page lifetime; brand filtering reads
  // the latest value via a ref so the connection is never torn down/reopened.
  useEffect(() => {
    const eventSource = endpoints.eventsStream();

    function shouldRefresh(event) {
      const activeBrandId = selectedBrandIdRef.current;
      if (!activeBrandId) return false;
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

  async function handleAccessCheck(source) {
    if (!source?.id) return;
    setError("");
    try {
      const result = await endpoints.sourceAccessCheck(source.id);
      const issues = Array.isArray(result.issues) ? result.issues : [];
      const reason = issues.includes("brand_bot_token_not_configured")
        ? "Bu source uchun brand bot tokeni yo'q; Telethon worker accessi hali tasdiqlanmagan."
        : issues.includes("channel_admin_required")
          ? "Kanal postlari uchun botni kanalga administrator qiling."
          : issues.includes("group_access_or_privacy_required")
            ? "Botni groupga qo'shing va BotFather orqali privacy mode'ni o'chiring."
            : "Telegram manziliga monitoring accessi tasdiqlanmadi.";
      setNotice(result.ok ? "Telegram monitoring accessi tasdiqlandi." : reason);
      await loadConnection(selectedBrandId);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleToggleSource(source) {
    await endpoints.updateSource(source.id, { active: !source.active });
    await loadDashboard(selectedBrandId);
  }

  async function handleRefreshSource(source) {
    const result = await endpoints.refreshSource(source.id);
    setNotice(`${result.source?.title || source.title || "Telegram source"} refresh qilindi.`);
    await loadDashboard(selectedBrandId);
  }

  async function handleBackfillSource(source) {
    try {
      await endpoints.refreshSource(source.id);
    } catch {}
    const result = await endpoints.backfillSource(source.id, { comments_per_post: 50 });
    setNotice(result.ok === false
      ? result.error || "Backfill yakunlanmadi."
      : `${result.posts_seen || 0} ta post va ${result.comments_seen || 0} ta comment tekshirildi.`);
    await loadDashboard(selectedBrandId);
  }

  function handleBrandChange(brandId) {
    const nextBrandId = saveSelectedBrandId(brandId);
    selectedBrandIdRef.current = nextBrandId;
    setSelectedBrandId(nextBrandId);
    setConnection(null);
    setSetupResult(null);
    setError("");
    setNotice("");
  }

  function handleOpenSetup() {
    if (!selectedBrandId) {
      setError("Telegram ulashdan oldin brandni tanlang.");
      return;
    }
    setSetupResult(null);
    setIsAddModalOpen(true);
    if (selectedBrandId !== lastLoadedConnectionBrandId.current) {
      loadConnection(selectedBrandId).catch((err) => setError(err.message));
    }
  }

  async function handleSetup(payload) {
    if (!selectedBrandId) {
      const failure = { ok: false, message: "Telegram ulashdan oldin brandni tanlang." };
      setSetupResult(failure);
      return failure;
    }
    setSetupSaving(true);
    setError("");
    setNotice("");
    try {
      const response = await endpoints.telegramSetup(selectedBrandId, payload);
      setConnection(response);
      lastLoadedConnectionBrandId.current = selectedBrandId;
      setSetupResult({
        ...response,
        ok: true,
        message: "Telegram bot, kanal va discussion sozlamalari saqlandi.",
      });
      clearApiCache(["/telegram/", "/dashboard/summary", "/mentions"]);
      await loadDashboard(selectedBrandId);
      setNotice("Telegram bot, kanal va discussion sozlamalari saqlandi.");
      return response;
    } catch (err) {
      const failure = { ok: false, message: err.message };
      setSetupResult(failure);
      setError(err.message);
      return failure;
    } finally {
      setSetupSaving(false);
    }
  }

  async function handleDeleteConnection() {
    if (!selectedBrandId || !window.confirm("Brandning Telegram bot connectioni uzilsinmi? Kanal va group source'lari o'chirilmaydi.")) return;
    setConnectionDeleting(true);
    setError("");
    setNotice("");
    try {
      const deleted = await endpoints.telegramDeleteConnection(selectedBrandId);
      const refreshed = await loadConnection(selectedBrandId);
      const message = deleted.connection_deleted
        ? "Telegram bot connection uzildi. Kanal va group source'lari saqlanib qoldi."
        : "Bu brandda uziladigan Telegram bot connection topilmadi.";
      setSetupResult({ ...refreshed, ok: true, message });
      setNotice(message);
    } catch (err) {
      setError(err.message);
    } finally {
      setConnectionDeleting(false);
    }
  }

  function handleDeleteSource(source) {
    setPendingDelete(source);
  }

  async function confirmDeleteSource(purgeMentions) {
    const source = pendingDelete;
    if (!source) return;
    setError("");
    setNotice("");
    setDeleteBusy(true);
    try {
      const deleted = await endpoints.deleteSource(source.id, purgeMentions);
      setNotice(
        purgeMentions
          ? `${deleted.sources_deleted} ta source, ${deleted.mentions_deleted} ta post/comment va ${deleted.analyses_deleted} ta AI tahlil o'chirildi.`
          : `${deleted.sources_deleted} ta source o'chirildi. ${deleted.mentions_retained} ta tahlil qilingan mention saqlandi — bu kanalni qayta ulasangiz ular qayta tahlil qilinmaydi.`,
      );
      setPendingDelete(null);
      await Promise.all([loadDashboard(selectedBrandId), loadConnection(selectedBrandId)]);
    } catch (err) {
      setError(err.message || "Source o'chirishda xatolik yuz berdi.");
    } finally {
      setDeleteBusy(false);
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

        <section className="panel activeBrandToolbar">
          <div>
            <strong>Faol brand</strong>
            <p>Faqat shu brand bo‘yicha Telegram ma’lumotlari.</p>
          </div>
          <SmartSelect
            value={selectedBrandId}
            options={brands.map((brand) => ({ value: brand.id, label: brand.name }))}
            onChange={handleBrandChange}
            emptyLabel="Brand mavjud emas"
            ariaLabel="Telegram uchun faol brandni tanlash"
          />
          <a className="button secondary linkButton" href="/profile">
            <Link2 size={16} />
            <span>Profil</span>
          </a>
        </section>

        {!loading && !selectedBrandId && (
          <div className="errorBanner">Monitoringni ko'rish va Telegram ulash uchun avval brand yarating yoki tanlang.</div>
        )}

        <StatsBar sources={visibleSources} summary={summary} loading={isInitialLoading} />
        <MonitoringInsights platform="telegram" sources={visibleSources} summary={summary} loading={isInitialLoading} />

        <section className="monitoringWorkspace">
          <SourceBoard
            categories={categories}
            sources={visibleSources}
            selectedCategoryKey={selectedCategoryKey}
            onCategoryChange={setSelectedCategoryKey}
            onOpenAdd={handleOpenSetup}
            onToggleSource={handleToggleSource}
            onCheckSource={handleAccessCheck}
            onRefreshSource={handleRefreshSource}
            onBackfillSource={handleBackfillSource}
            onDeleteSource={handleDeleteSource}
            loading={isInitialLoading}
          />

          <RecentMentions mentions={mentions} loading={isInitialLoading} />
        </section>

        <MentionsAnalysisPanels
          mentions={mentions}
          loading={isInitialLoading}
          platformLabel="Telegram"
        />

        <DeleteSourceModal
          open={Boolean(pendingDelete)}
          sourceName={
            pendingDelete
              ? pendingDelete.title ||
                (pendingDelete.username ? `@${pendingDelete.username}` : pendingDelete.chat_id) ||
                "Telegram source"
              : ""
          }
          busy={deleteBusy}
          onCancel={() => setPendingDelete(null)}
          onConfirm={confirmDeleteSource}
        />

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
                  <h2 id="add-source-title">Telegram ulanishini sozlash</h2>
                  <p>Bot, rasmiy kanal va discussion groupni tanlangan brandga mustaqil ulang.</p>
                </div>
                <button className="iconButton" type="button" aria-label="Yopish" onClick={() => setIsAddModalOpen(false)}>
                  <X size={18} />
                </button>
              </div>
              <div className="modalContent">
                {connectionLoading ? (
                  <div className="loadingBar">Telegram ulanish holati yuklanmoqda...</div>
                ) : (
                  <TelegramConnectionForm
                    selectedBrandId={selectedBrandId}
                    selectedBrandName={brands.find((brand) => brand.id === selectedBrandId)?.name || ""}
                    initialConnection={connection}
                    result={setupResult}
                    onSubmit={handleSetup}
                    onDelete={handleDeleteConnection}
                    saving={setupSaving}
                    deleting={connectionDeleting}
                  />
                )}
              </div>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}

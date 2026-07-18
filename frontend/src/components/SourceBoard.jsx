import {
  Bot,
  Building2,
  CheckCircle2,
  Newspaper,
  Pause,
  Play,
  RadioTower,
  RefreshCw,
  Search,
  ShieldAlert,
  DownloadCloud,
  Plus,
  Star,
  Trash2,
  Users,
  Zap,
} from "lucide-react";
import { useMemo } from "react";

const iconByCategory = {
  owned: RadioTower,
  bot: Bot,
  competitor: Building2,
  news: Newspaper,
  industry: Zap,
  influencer: Star,
  community: Users,
  useful: CheckCircle2,
  risk: ShieldAlert,
  unknown: Search,
};

const categoryOrder = ["owned", "bot", "competitor", "news", "industry", "influencer", "community", "useful", "risk", "unknown"];

const sourceKindLabels = {
  channel: "Kanal",
  group: "Guruh",
  supergroup: "Superguruh",
  private: "Private chat",
  bot: "Bot",
  unknown: "Turi noma'lum",
};

const monitoringModeLabels = {
  all_messages: "Barcha xabarlar",
  brand_matches_only: "Faqat brand mos",
};

function sourceRef(source) {
  if (source.username) return `@${source.username}`;
  if (source.chat_id) return String(source.chat_id);
  return "unresolved";
}

function sourceTitle(source) {
  return source.title || source.competitor_name || sourceRef(source);
}

function sourceKindLabel(value) {
  return sourceKindLabels[value] || value || "Turi noma'lum";
}

function monitoringModeLabel(value) {
  return monitoringModeLabels[value] || value || "Qamrov noma'lum";
}

export function SourceBoard({
  categories,
  sources,
  selectedCategoryKey,
  onCategoryChange,
  onOpenAdd,
  onToggleSource,
  onCheckSource,
  onRefreshSource,
  onBackfillSource,
  onDeleteSource,
  loading = false,
}) {
  const orderedCategories = useMemo(
    () => categories.slice().sort((a, b) => categoryOrder.indexOf(a.key) - categoryOrder.indexOf(b.key)),
    [categories],
  );
  const counts = sources.reduce(
    (acc, source) => {
      const key = source.source_category || "unknown";
      acc.all += 1;
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    },
    { all: 0 },
  );
  const selectedCategory =
    orderedCategories.find((category) => category.key === selectedCategoryKey) || orderedCategories[0];
  const selectedSources = sources.filter((source) => (source.source_category || "unknown") === selectedCategory?.key);
  const SelectedIcon = iconByCategory[selectedCategory?.key] || Search;

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
            <article className="sourceRow skeletonRow" key={`source-skeleton-${index}`}>
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
          <span>Telegram papkalari</span>
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
            <SourceRow
              key={source.id}
              source={source}
              onToggleSource={onToggleSource}
              onCheckSource={onCheckSource}
              onRefreshSource={onRefreshSource}
              onBackfillSource={onBackfillSource}
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

function SourceRow({ source, onToggleSource, onCheckSource, onRefreshSource, onBackfillSource, onDeleteSource }) {
  const isBotInbox = source.source_role === "bot_inbox";
  const connectorAccessReady = source.telethon_access_status === "ready";
  const stateClass = !source.active ? "neutral" : source.connector_managed && !connectorAccessReady ? "warn" : "ok";
  const stateLabel = !source.active
    ? "paused"
    : source.connector_managed && !connectorAccessReady
      ? "access/transportni tekshiring"
      : source.connector_managed
        ? "monitoring"
        : "yoqilgan";
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
        {source.linked_discussion_chat_id && <span className="blue" title="Kanalga discussion group ulangan">Discuss ulangan</span>}
        {source.collect_posts && <span title="Kanal/guruh postlari olinadi">Postlar</span>}
        {source.collect_comments && <span title="Discussion yoki group commentlari olinadi">Commentlar</span>}
      </div>
      <em className={`state ${stateClass}`}>{stateLabel}</em>
      <div className="rowActions">
        {isBotInbox ? (
          <span className="sourceManagedHint">Bot connector orqali boshqariladi</span>
        ) : (
          <>
            <button className="miniButton" type="button" onClick={() => onCheckSource(source)} title="Aynan shu brand botining access holatini tekshiradi">
              <Search size={15} />
              <span>Tekshirish</span>
            </button>
            <button className="miniButton" type="button" onClick={() => onRefreshSource(source)} title="Source nomi, username va linked chat ma'lumotini yangilaydi">
              <RefreshCw size={15} />
              <span>Yangilash</span>
            </button>
            <button className="miniButton" type="button" onClick={() => onBackfillSource(source)} title="Kuzatuv sanasidan boshlab post/commentlarni qayta olib keladi">
              <DownloadCloud size={15} />
              <span>To'liq olish</span>
            </button>
            <button className="miniButton" type="button" onClick={() => onToggleSource(source)} title={source.active ? "Kuzatuvni vaqtincha to'xtatadi" : "Kuzatuvni qayta yoqadi"}>
              {source.active ? <Pause size={15} /> : <Play size={15} />}
              <span>{source.active ? "Pauza" : "Davom"}</span>
            </button>
            <button className="miniButton danger" type="button" onClick={() => onDeleteSource(source)} title="Source va unga tegishli barcha post, comment hamda AI tahlillarini o'chiradi">
              <Trash2 size={15} />
              <span>O'chirish</span>
            </button>
          </>
        )}
      </div>
      {(source.notes || source.competitor_name) && (
        <p className="sourceRowNote">{source.notes || source.competitor_name}</p>
      )}
    </article>
  );
}

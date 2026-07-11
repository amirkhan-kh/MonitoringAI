import { CheckCircle2, Plus, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

const monitoringModeLabels = {
  all_messages: "Barcha xabarlar",
  brand_matches_only: "Faqat brand mos kelganlar",
};

function todayInputValue() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 10);
}

export function SourceForm({
  categories,
  selectedBrandId,
  initialCategory = "owned",
  onAccessCheck,
  onImport,
  accessResult,
  sourceResult,
}) {
  const [sourceRef, setSourceRef] = useState("");
  const [category, setCategory] = useState(initialCategory);
  const [mode, setMode] = useState("all_messages");
  const [competitorName, setCompetitorName] = useState("");
  const [notes, setNotes] = useState("");
  const [collectPosts, setCollectPosts] = useState(true);
  const [collectComments, setCollectComments] = useState(true);
  const [monitorFrom, setMonitorFrom] = useState(todayInputValue);

  const categoryMeta = useMemo(() => categories.find((item) => item.key === category), [categories, category]);

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

  async function handleSubmit(event) {
    event.preventDefault();
    if (!sourceRef.trim()) return;
    const line = [sourceRef, category, mode, competitorName, notes, monitorFrom]
      .map((value) => `"${String(value || "").replaceAll('"', '""')}"`)
      .join(",");
    await onImport({
      brand_id: selectedBrandId || null,
      raw_text: line,
      default_source_category: category,
      default_monitoring_mode: mode,
      default_monitor_from: monitorFrom,
      collect_posts: collectPosts,
      collect_comments: collectComments,
    });
    setSourceRef("");
    setCompetitorName("");
    setNotes("");
  }

  return (
    <form className="sourceForm" onSubmit={handleSubmit}>
      <div className="panelHeader">
        <div>
          <h2>Manzil qo'shish</h2>
          <p>{categoryMeta?.description || "Brand uchun Telegram manba qo'shing."}</p>
        </div>
        <span className={accessResult?.ok ? "pill ok" : "pill neutral"}>{accessResult ? "checked" : "ready"}</span>
      </div>

      <label className="field">
        <span>Kanal, chat yoki bot</span>
        <input
          className="input"
          value={sourceRef}
          onChange={(event) => setSourceRef(event.target.value)}
          placeholder="Kanal, guruh, bot username/linki yoki chat ID kiriting"
          required
        />
        <p className="fieldHint">Username, kanal linki, group/chat ID yoki bot username kiriting.</p>
      </label>

      <div className="formGrid">
        <label className="field">
          <span>Papka</span>
          <select className="input select" value={category} onChange={(event) => handleCategory(event.target.value)}>
            {categories.map((item) => (
              <option key={item.key} value={item.key}>
                {item.label}
              </option>
            ))}
          </select>
          <p className="fieldHint">Source dashboardda qaysi bo'limda turishini belgilaydi.</p>
        </label>
        <label className="field">
          <span>Qamrov</span>
          <select className="input select" value={mode} onChange={(event) => setMode(event.target.value)}>
            <option value="all_messages">{monitoringModeLabels.all_messages}</option>
            <option value="brand_matches_only">{monitoringModeLabels.brand_matches_only}</option>
          </select>
          <p className="fieldHint">Barcha xabarlar yoki faqat brand nomi topilgan xabarlar olinadi.</p>
        </label>
        <label className="field">
          <span>Kuzatuv sanasi</span>
          <input
            className="input"
            type="date"
            value={monitorFrom}
            onChange={(event) => setMonitorFrom(event.target.value)}
            required
          />
          <p className="fieldHint">To'liq olish shu sanadan bugungacha bo'lgan xabarlarni import qiladi.</p>
        </label>
      </div>

      {category === "competitor" && (
        <label className="field">
          <span>Raqobatchi nomi</span>
          <input
            className="input"
            value={competitorName}
            onChange={(event) => setCompetitorName(event.target.value)}
            placeholder="Bu source qaysi raqobatchiga tegishli ekanini yozing"
          />
        </label>
      )}

      <label className="field full">
        <span>Izoh</span>
        <textarea
          className="input textarea"
          rows="3"
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          placeholder="Source haqida ichki eslatma yoki access bo'yicha izoh yozing"
        />
        <p className="fieldHint">Source haqida ichki eslatma. Monitoring filtriga ta'sir qilmaydi.</p>
      </label>

      <div className="checks">
        <label>
          <input type="checkbox" checked={collectPosts} onChange={(event) => setCollectPosts(event.target.checked)} />
          <span>Postlar</span>
        </label>
        <label>
          <input type="checkbox" checked={collectComments} onChange={(event) => setCollectComments(event.target.checked)} />
          <span>Commentlar</span>
        </label>
      </div>

      <div className="buttonRow">
        <button className="button secondary" type="button" onClick={() => onAccessCheck(sourceRef)}>
          <Search size={17} />
          <span>Access tekshirish</span>
        </button>
        <button className="button primary" type="submit">
          <Plus size={17} />
          <span>Qo'shish</span>
        </button>
      </div>

      {(accessResult || sourceResult) && (
        <StatusPanel accessResult={accessResult} sourceResult={sourceResult} />
      )}
    </form>
  );
}

function yesNo(value) {
  return value ? "Ha" : "Yo'q";
}

const issueText = {
  bot_not_member_or_no_access: "Bot access yo'q; import Telethon user-session orqali davom etadi.",
  group_access_or_privacy_required: "Bot group update ololmayapti; live import uchun Telethon user-session ishlatiladi.",
  channel_admin_required: "Bot API kanal postini adminsiz olmaydi; Telethon live sync public/member kanal postlarini import qiladi.",
  linked_discussion_not_found: "Kanalga linked discussion group ulanmagan.",
  discussion_group_access_required: "Bot linked discussion group ichida emas; Telethon access bo'lsa commentlarni olib ko'radi.",
  chat_not_found_or_bot_has_no_access: "Bot access yo'q; source linki Telethon uchun katalogga qo'shiladi.",
  unsupported_chat_type: "Bu chat turi hozircha qo'llab-quvvatlanmaydi.",
};

function readableIssues(issues = []) {
  return issues.map((issue) => issueText[issue] || issue);
}

function StatusPanel({ accessResult, sourceResult }) {
  const source = sourceResult?.source;
  const backfill = sourceResult?.backfill;
  const access = sourceResult?.access || accessResult;

  return (
    <div className="statusPanel">
      <div className="statusTitle">
        <CheckCircle2 size={18} />
        <strong>{source?.title || access?.chat_title || access?.chat_id_or_username}</strong>
      </div>
      <div className="statusGrid">
        <span>Bot post access</span>
        <strong>{yesNo(access?.can_read_posts)}</strong>
        <span>Bot comment access</span>
        <strong>{yesNo(access?.can_read_comments)}</strong>
        <span>Import usuli</span>
        <strong>{access?.ok ? "Bot API + Telethon" : "Telethon"}</strong>
        <span>Linked chat</span>
        <strong>{access?.linked_discussion_chat_id || source?.linked_discussion_chat_id || "Yo'q"}</strong>
        <span>Bot status</span>
        <strong>{access?.bot_status || "-"}</strong>
      </div>
      {source?.description && <p className="statusDescription">{source.description}</p>}
      {!!access?.issues?.length && <p className="statusWarning">{readableIssues(access.issues).join(" ")}</p>}
      {backfill && (
        <div className={backfill.ok ? "backfillResult ok" : "backfillResult bad"}>
          <strong>{backfill.ok ? "To'liq olish yakunlandi" : "To'liq olish uchun Telethon login kerak"}</strong>
          <span>
            Posts: {backfill.posts_seen || 0} · Comments: {backfill.comments_seen || 0}
          </span>
          {backfill.error && <small>{backfill.error.replace("Run backend/scripts/telegram_login.py first.", "Avval Telegram user session login qilinishi kerak.")}</small>}
        </div>
      )}
      {sourceResult?.error && <p className="statusWarning">{sourceResult.error}</p>}
    </div>
  );
}

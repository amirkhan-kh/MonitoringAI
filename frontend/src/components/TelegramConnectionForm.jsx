import {
  Bot,
  CheckCircle2,
  Eye,
  EyeOff,
  MessageSquareText,
  RadioTower,
  Save,
  ShieldAlert,
  Trash2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

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

function connectorNode(data, role) {
  if (!data) return null;
  if (data[role]) return data[role];
  if (role === "bot" && data.bot_connection) return data.bot_connection;
  if (role === "bot" && data.connection) return data.connection;
  const rows = Array.isArray(data.sources)
    ? data.sources
    : Array.isArray(data.items)
      ? data.items
      : [];
  const aliases = role === "discussion" ? ["discussion", "linked_discussion"] : [role];
  return rows.find((item) => aliases.includes(item.source_role || item.role || item.source?.source_role)) || null;
}

function nestedSource(node) {
  return node?.source || node || null;
}

function sourceReference(node) {
  const source = nestedSource(node);
  if (!source) return "";
  if (source.bot_link) return source.bot_link;
  if (source.username) return `https://t.me/${String(source.username).replace(/^@/, "")}`;
  if (source.chat_id) return String(source.chat_id);
  return source.ref || source.link || source.chat_ref || "";
}

function connectorTitle(node, role) {
  const source = nestedSource(node);
  if (!source) return "Kiritilmagan";
  if (role === "bot") {
    const username = source.bot_username || source.username;
    return username ? `@${String(username).replace(/^@/, "")}` : source.bot_link || "Bot ulangan";
  }
  return source.title || source.chat_title || sourceReference(source) || "Ulangan";
}

function connectorStatus(node) {
  if (!node) return "kiritilmagan";
  if (node.error || node.ok === false) return "xato";
  const source = nestedSource(node);
  return node.status || source?.status || (source?.active === false ? "pause" : node.ok ? "ulangan" : "active");
}

function capabilityText(value) {
  if (!value) return "";
  if (Array.isArray(value)) return value.filter(Boolean).join(" · ");
  if (typeof value === "string") return value;
  if (typeof value === "object") {
    return Object.entries(value)
      .filter(([, enabled]) => Boolean(enabled))
      .map(([name]) => name.replaceAll("_", " "))
      .join(" · ");
  }
  return "";
}

function responseCapabilityText(capabilities, role) {
  if (!capabilities || typeof capabilities !== "object") return "";
  const definitions = role === "bot"
    ? [["bot_reference", "profil reference"], ["bot_polling", "update polling"]]
    : role === "channel"
      ? [["channel_monitoring", "kanal monitoring"], ["history_backfill", "history backfill"]]
      : [["discussion_monitoring", "discussion monitoring"], ["history_backfill", "history backfill"]];
  return definitions.filter(([key]) => capabilities[key]).map(([, label]) => label).join(" · ");
}

function readableWarning(value) {
  const warnings = {
    bot_link_is_reference_only_without_token: "Bot token berilmagan: bot faqat reference sifatida saqlandi.",
    bot_polling_is_disabled_in_reference_mode: "Reference rejimida bot polling o'chirilgan.",
    bot_connection_invalid: "Bot connection yaroqsiz; tokenni tekshiring.",
    bot_connection_conflict: "Bot connection boshqa polling yoki webhook bilan to'qnashmoqda.",
    bot_connection_rate_limited: "Telegram bot so'rovlari vaqtincha cheklangan.",
    bot_connection_encryption_error: "Saqlangan bot tokenini server o'qiy olmadi.",
    bot_inbox_missing_reconnect_required: "Bot inbox source topilmadi; bot connectionni qayta saqlang.",
    channel_is_cataloged_until_resolved: "Kanal saqlandi, lekin Telegram chat ID hali aniqlanmadi.",
    discussion_is_cataloged_until_resolved: "Discussion group saqlandi, lekin Telegram chat ID hali aniqlanmadi.",
    group_is_cataloged_until_resolved: "Group saqlandi, lekin Telegram chat ID hali aniqlanmadi.",
    discussion_group_auto_discovered: "Kanalga ulangan discussion group avtomatik topildi.",
    discussion_ref_differs_from_telegram_linked_chat: "Kiritilgan group kanalning Telegram'dagi linked chatidan farq qiladi.",
    telegram_monitoring_requires_bot_access_or_telethon_session: "Post va commentlarni olish uchun bot access yoki authorized Telethon session kerak.",
    telethon_history_requires_an_authorized_session_with_chat_access: "Tarixiy backfill uchun Telethon session chatga kirish huquqiga ega bo'lishi kerak.",
    global_bot_uses_legacy_worker: "Bu serverning global boti: update oqimini legacy Telegram worker boshqaradi.",
    global_bot_webhook_blocks_legacy_polling: "Global botda faol webhook bor; legacy polling ishlamaydi.",
    channel_bot_access_denied: "Bot kanal postlarini o'qish huquqiga ega emas; uni kanal administratori qiling.",
    discussion_bot_access_denied: "Bot discussion group xabarlarini o'qish huquqiga ega emas.",
    channel_monitoring_not_verified: "Kanal monitoringi hali bot yoki Telethon worker tomonidan tasdiqlanmagan.",
    discussion_monitoring_not_verified: "Discussion monitoringi hali bot yoki Telethon worker tomonidan tasdiqlanmagan.",
    telethon_access_is_unverified_until_worker_reads_chat: "Telethon access worker chatni muvaffaqiyatli o'qigandan keyin tasdiqlanadi.",
  };
  return warnings[value] || String(value || "").replaceAll("_", " ");
}

function ConnectorStatusCards({ data }) {
  const definitions = [
    { key: "bot", label: "Bot", Icon: Bot },
    { key: "channel", label: "Kanal", Icon: RadioTower },
    { key: "discussion", label: "Discussion group", Icon: MessageSquareText },
  ];
  const capabilities = data?.capabilities || {};
  const globalWarnings = Array.isArray(data?.warnings) ? data.warnings : [];

  return (
    <div className="telegramConnectionResults full">
      <div className="telegramConnectorStatusGrid">
        {definitions.map(({ key, label, Icon }) => {
          const node = connectorNode(data, key);
          const source = nestedSource(node);
          const isCatalogOnly = key !== "bot" && node && source?.chat_id == null;
          const roleCapability = key === "channel"
            ? Boolean(capabilities.channel_monitoring)
            : key === "discussion"
              ? Boolean(capabilities.discussion_monitoring)
              : Boolean(capabilities.bot_polling);
          const status = isCatalogOnly
            ? "catalog"
            : key !== "bot" && node
              ? roleCapability ? "monitoring" : "access kutilmoqda"
              : connectorStatus(node);
          const detail = node?.status_detail || node?.message || node?.error || nestedSource(node)?.status_detail || "";
          const nodeWarnings = Array.isArray(node?.warnings) ? node.warnings : [];
          const capability = capabilityText(node?.capabilities) || responseCapabilityText(capabilities, key);
          const normalizedStatus = String(node?.status || "").toLowerCase();
          const hasBadStatus = ["error", "failed", "invalid", "unauthorized", "conflict"].some((value) => normalizedStatus.includes(value));
          const hasWarningStatus = isCatalogOnly
            || (key !== "bot" && node && !roleCapability)
            || ["suspended", "degraded", "pending", "rate_limited", "ready", "reference", "webhook"].some((value) => normalizedStatus.includes(value));
          const tone = node?.error || node?.ok === false || hasBadStatus
            ? "bad"
            : hasWarningStatus
              ? "warn"
              : node
                ? "ok"
                : "neutral";
          return (
            <article className={`telegramConnectorStatus ${tone}`} key={key}>
              <span className="telegramConnectorStatusIcon"><Icon size={17} /></span>
              <div>
                <strong>{label}</strong>
                <span>{connectorTitle(node, key)}</span>
              </div>
              <em className={`state ${tone}`}>{status}</em>
              {capability && <small>{capability}</small>}
              {detail && <p>{detail}</p>}
              {!!nodeWarnings.length && <p className="statusWarning">{nodeWarnings.map(readableWarning).join(" ")}</p>}
            </article>
          );
        })}
      </div>
      {!!globalWarnings.length && (
        <div className="telegramConnectionWarnings">
          <ShieldAlert size={16} />
          <span>{globalWarnings.map(readableWarning).join(" ")}</span>
        </div>
      )}
    </div>
  );
}

export function TelegramConnectionForm({
  selectedBrandId,
  selectedBrandName = "",
  initialConnection = null,
  result = null,
  onSubmit,
  onDelete = null,
  saving = false,
  deleting = false,
  submitLabel = "Telegram ulanishini saqlash",
}) {
  const [botLink, setBotLink] = useState("");
  const [botToken, setBotToken] = useState("");
  const [botMode, setBotMode] = useState("reference");
  const [botModeTouched, setBotModeTouched] = useState(false);
  const [channelRef, setChannelRef] = useState("");
  const [discussionRef, setDiscussionRef] = useState("");
  const [monitorFrom, setMonitorFrom] = useState(todayInputValue);
  const [collectPosts, setCollectPosts] = useState(true);
  const [collectComments, setCollectComments] = useState(true);
  const [showToken, setShowToken] = useState(false);
  const [validationError, setValidationError] = useState("");

  useEffect(() => {
    const bot = connectorNode(initialConnection, "bot");
    const channel = connectorNode(initialConnection, "channel");
    const discussion = connectorNode(initialConnection, "discussion");
    const source = nestedSource(channel) || nestedSource(discussion);
    setBotLink(sourceReference(bot));
    setBotToken("");
    setBotMode(bot?.mode || nestedSource(bot)?.mode || "reference");
    setBotModeTouched(false);
    setChannelRef(sourceReference(channel));
    setDiscussionRef(sourceReference(discussion));
    setMonitorFrom(dateInputValue(initialConnection?.monitor_from || source?.monitor_from));
    setCollectPosts(initialConnection?.collect_posts ?? source?.collect_posts ?? true);
    setCollectComments(initialConnection?.collect_comments ?? source?.collect_comments ?? true);
    setShowToken(false);
    setValidationError("");
  }, [initialConnection, selectedBrandId]);

  const statusData = result?.ok === false ? initialConnection : result || initialConnection;
  const hasBotConnection = useMemo(
    () => Boolean(connectorNode(initialConnection, "bot")),
    [initialConnection],
  );
  const hasConfiguredBotToken = useMemo(() => {
    const bot = connectorNode(initialConnection, "bot");
    return Boolean(bot?.token_configured || nestedSource(bot)?.token_configured);
  }, [initialConnection]);

  async function handleSubmit(event) {
    event.preventDefault();
    const normalized = {
      botLink: botLink.trim(),
      botToken: botToken.trim(),
      channelRef: channelRef.trim(),
      discussionRef: discussionRef.trim(),
    };
    if (!selectedBrandId) {
      setValidationError("Avval brandni tanlang.");
      return;
    }
    if (!Object.values(normalized).some(Boolean)) {
      setValidationError("Bot link/token, kanal yoki discussion groupdan kamida bittasini kiriting.");
      return;
    }
    if (
      botMode === "polling"
      && !normalized.botToken
      && !hasConfiguredBotToken
    ) {
      setValidationError("Dedicated polling rejimi uchun bot token kerak.");
      return;
    }

    setValidationError("");
    const payload = {
      monitor_from: monitorFrom,
      collect_posts: collectPosts,
      collect_comments: collectComments,
    };
    if (botModeTouched || normalized.botLink || normalized.botToken) payload.bot_mode = botMode;
    if (normalized.botLink) payload.bot_link = normalized.botLink;
    if (normalized.botToken) payload.bot_token = normalized.botToken;
    if (normalized.channelRef) payload.channel_ref = normalized.channelRef;
    if (normalized.discussionRef) payload.discussion_ref = normalized.discussionRef;
    const outcome = await onSubmit(payload);
    if (outcome?.ok !== false) setBotToken("");
  }

  return (
    <form className="sourceForm telegramConnectionForm" onSubmit={handleSubmit}>
      <div className={`telegramSelectedBrand full ${selectedBrandId ? "ready" : "missing"}`}>
        {selectedBrandId ? <CheckCircle2 size={17} /> : <ShieldAlert size={17} />}
        <div>
          <span>Tanlangan brand</span>
          <strong>{selectedBrandName || selectedBrandId || "Brand tanlanmagan"}</strong>
        </div>
      </div>

      <div className="telegramConnectorInputs full">
        <section className="telegramConnectorInputCard bot">
          <div className="telegramConnectorInputHead">
            <Bot size={18} />
            <div>
              <strong>Telegram bot</strong>
              <span>Link va tokendan biri yoki ikkalasi</span>
            </div>
          </div>
          <label className="field">
            <span>Bot link yoki username</span>
            <input
              className="input"
              value={botLink}
              onChange={(event) => setBotLink(event.target.value)}
              placeholder="https://t.me/brand_bot"
              autoComplete="off"
              spellCheck="false"
            />
          </label>
          <label className="field">
            <span>Bot token</span>
            <div className="tokenInputWrap">
              <input
                className="input"
                type={showToken ? "text" : "password"}
                value={botToken}
                onChange={(event) => setBotToken(event.target.value)}
                placeholder={hasBotConnection ? "Yangi token bilan almashtirish" : "123456:ABC…"}
                autoComplete="off"
                spellCheck="false"
              />
              <button
                className="eyeBtn"
                type="button"
                onClick={() => setShowToken((current) => !current)}
                aria-label={showToken ? "Tokenni yashirish" : "Tokenni ko'rsatish"}
              >
                {showToken ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            <p className="fieldHint">Token faqat serverga yuboriladi; brauzer xotirasida saqlanmaydi.</p>
          </label>
          <label className="field">
            <span>Bot ishlash rejimi</span>
            <select
              className="input select"
              value={botMode}
              onChange={(event) => {
                setBotMode(event.target.value);
                setBotModeTouched(true);
              }}
            >
              <option value="reference">Reference — faqat rasmiy bot profili</option>
              <option value="polling">Dedicated polling — xabarlarni olish</option>
            </select>
          </label>
          <div className={`telegramBotModeWarning ${botMode}`}>
            <ShieldAlert size={16} />
            <span>
              {botMode === "polling"
                ? "Faqat MonitoringAI uchun ajratilgan botni ulang. Production bot webhooki yoki boshqa poller bilan bir token bir vaqtda ishlamaydi."
                : "Reference rejimi bot profilini registrga qo'shadi; private bot suhbatlari olinmaydi."}
            </span>
          </div>
        </section>

        <section className="telegramConnectorInputCard channel">
          <div className="telegramConnectorInputHead">
            <RadioTower size={18} />
            <div>
              <strong>Rasmiy kanal</strong>
              <span>Mustaqil ulanadi</span>
            </div>
          </div>
          <label className="field">
            <span>Kanal linki, username yoki ID</span>
            <input
              className="input"
              value={channelRef}
              onChange={(event) => setChannelRef(event.target.value)}
              placeholder="https://t.me/brand_channel"
              autoComplete="off"
              spellCheck="false"
            />
            <p className="fieldHint">Faqat kanal mavjud bo'lsa ham setup saqlanadi.</p>
          </label>
        </section>

        <section className="telegramConnectorInputCard discussion">
          <div className="telegramConnectorInputHead">
            <MessageSquareText size={18} />
            <div>
              <strong>Discussion group</strong>
              <span>Mustaqil ulanadi</span>
            </div>
          </div>
          <label className="field">
            <span>Group linki, username yoki ID</span>
            <input
              className="input"
              value={discussionRef}
              onChange={(event) => setDiscussionRef(event.target.value)}
              placeholder="https://t.me/brand_chat"
              autoComplete="off"
              spellCheck="false"
            />
            <p className="fieldHint">Kanal bo'lmasa ham group comment/chat oqimi alohida ulanadi.</p>
          </label>
        </section>
      </div>

      <div className="formGrid full">
        <label className="field">
          <span>Kuzatuv sanasi</span>
          <input
            className="input"
            type="date"
            value={monitorFrom}
            onChange={(event) => setMonitorFrom(event.target.value)}
          />
        </label>
        <div className="checks telegramConnectionChecks">
          <label>
            <input type="checkbox" checked={collectPosts} onChange={(event) => setCollectPosts(event.target.checked)} />
            <span>Postlarni olish</span>
          </label>
          <label>
            <input type="checkbox" checked={collectComments} onChange={(event) => setCollectComments(event.target.checked)} />
            <span>Comment/chat olish</span>
          </label>
        </div>
      </div>

      {validationError && (
        <div className="backfillResult bad full">
          <ShieldAlert size={16} />
          <span>{validationError}</span>
        </div>
      )}

      {result?.message && (
        <div className={result.ok === false ? "backfillResult bad full" : "backfillResult ok full"}>
          {result.ok === false ? <ShieldAlert size={16} /> : <CheckCircle2 size={16} />}
          <span>{result.message}</span>
        </div>
      )}

      {statusData && <ConnectorStatusCards data={statusData} />}

      <div className="buttonRow profileModalActions full">
        {onDelete && hasBotConnection && (
          <button className="button secondary telegramDisconnectButton" type="button" onClick={onDelete} disabled={saving || deleting}>
            <Trash2 size={16} />
            <span>{deleting ? "Uzilmoqda..." : "Bot connectionni uzish"}</span>
          </button>
        )}
        <button className="button primary" type="submit" disabled={saving || deleting || !selectedBrandId}>
          {saving ? <CheckCircle2 size={17} /> : <Save size={17} />}
          <span>{saving ? "Saqlanmoqda..." : submitLabel}</span>
        </button>
      </div>
    </form>
  );
}

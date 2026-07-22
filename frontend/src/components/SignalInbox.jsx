import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CheckCheck, ExternalLink, Eye, RefreshCw, RotateCcw, ShieldAlert } from "lucide-react";
import { clearApiCache, endpoints, getSession } from "../api/client";

/**
 * The dashboard twin of the staff-group Telegram cards.
 *
 * Same rows, same two actions (reviewed / answered) and the same "how many are still
 * unanswered" counter — pressing a button here re-renders the Telegram card, and pressing
 * it in Telegram shows up here, because both are views of one AlertEvent row.
 */

const riskLabels = { critical: "Kritik", high: "Yuqori", medium: "O'rta", low: "Past" };
const platformLabels = { telegram: "Telegram", youtube: "YouTube", instagram: "Instagram", facebook: "Facebook" };

function waitedText(iso) {
  if (!iso) return "-";
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (minutes < 60) return `${minutes} daq`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} soat ${minutes % 60} daq`;
  return `${Math.floor(hours / 24)} kun ${hours % 24} soat`;
}

function durationText(seconds) {
  if (seconds === null || seconds === undefined) return "-";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} daq`;
  return `${Math.floor(minutes / 60)} soat ${minutes % 60} daq`;
}

export function SignalInbox() {
  const [summary, setSummary] = useState(null);
  const [events, setEvents] = useState([]);
  const [tab, setTab] = useState("unanswered");
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");
  const [loading, setLoading] = useState(true);
  const tabRef = useRef(tab);
  const refreshTimer = useRef(null);

  tabRef.current = tab;

  const load = useCallback(async (nextTab = tabRef.current) => {
    setError("");
    try {
      const [summaryRow, eventRows] = await Promise.all([
        endpoints.alertSummary(),
        endpoints.alertEvents({ work_status: nextTab, limit: 30 }),
      ]);
      setSummary(summaryRow);
      setEvents(eventRows);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(tab);
  }, [tab, load]);

  // A press in the Telegram group publishes an alert_event, so the board follows along
  // without the operator refreshing anything.
  useEffect(() => {
    const stream = endpoints.eventsStream();
    function scheduleRefresh() {
      if (refreshTimer.current) return;
      refreshTimer.current = window.setTimeout(() => {
        refreshTimer.current = null;
        clearApiCache(["/alerts/"]);
        load(tabRef.current);
      }, 700);
    }
    stream.addEventListener("alert_event", scheduleRefresh);
    return () => {
      stream.close();
      if (refreshTimer.current) {
        window.clearTimeout(refreshTimer.current);
        refreshTimer.current = null;
      }
    };
  }, [load]);

  // The name recorded against the signal, so the Telegram card names a person either way.
  const actor = useMemo(() => {
    const session = getSession();
    return session?.display_name || session?.username || "Dashboard";
  }, []);

  async function act(eventId, action) {
    setBusyId(eventId);
    setError("");
    try {
      await endpoints.alertAction(eventId, action, actor);
      clearApiCache(["/alerts/"]);
      await load(tabRef.current);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId("");
    }
  }

  const open = summary?.open || 0;
  const bySource = summary?.by_source || [];

  return (
    <section className="signalInbox panel">
      <div className="sectionHeader">
        <div>
          <h2>Signal inbox — javob kutayotganlar</h2>
          <p>
            AI tahlildan o'tgan har bir mijoz izohi shu yerda va xodimlar Telegram guruhida yopiladi.
            Tugmalar ikkala joyda ham bir xil holatni yangilaydi.
          </p>
        </div>
        <button className="button secondary" type="button" onClick={() => { clearApiCache(["/alerts/"]); load(tab); }}>
          <RefreshCw size={17} />
          <span>Yangilash</span>
        </button>
      </div>

      <div className="signalStats">
        <div className={open ? "signalStat danger" : "signalStat ok"}>
          <ShieldAlert size={18} />
          <strong>{open}</strong>
          <span>Javob berilmagan</span>
        </div>
        <div className="signalStat">
          <Eye size={18} />
          <strong>{summary?.checked || 0}</strong>
          <span>Tekshirilgan, javob kutmoqda</span>
        </div>
        <div className="signalStat">
          <CheckCheck size={18} />
          <strong>{summary?.answered_today || 0}</strong>
          <span>Bugun yopildi</span>
        </div>
        <div className="signalStat">
          <RotateCcw size={18} />
          <strong>{durationText(summary?.avg_response_seconds)}</strong>
          <span>O'rtacha javob vaqti</span>
        </div>
      </div>

      {bySource.length > 0 && (
        <div className="signalSources">
          <span>Kanallar bo'yicha:</span>
          {bySource.map((row) => (
            <span className="pill neutral" key={row.source}>
              {row.source} · {row.count}
            </span>
          ))}
        </div>
      )}

      {(summary?.by_person || []).length > 0 && (
        <div className="signalSources">
          <span>Bugungi xodimlar:</span>
          {summary.by_person.map((row) => (
            <span className="pill ok" key={row.name}>
              {row.name} · {row.count}
            </span>
          ))}
        </div>
      )}

      <div className="periodTabs" role="tablist" aria-label="Signal filtri">
        <button type="button" className={tab === "unanswered" ? "active" : ""} onClick={() => setTab("unanswered")}>
          Ochiq
        </button>
        <button type="button" className={tab === "checked" ? "active" : ""} onClick={() => setTab("checked")}>
          Tekshirilgan
        </button>
        <button type="button" className={tab === "answered" ? "active" : ""} onClick={() => setTab("answered")}>
          Yopilgan
        </button>
      </div>

      {error && <div className="errorBanner">{error}</div>}

      {loading ? (
        <div className="emptyState">Yuklanmoqda…</div>
      ) : events.length === 0 ? (
        <div className="emptyState">
          {tab === "answered" ? "Hali yopilgan signal yo'q." : "✅ Javob kutayotgan signal yo'q — barchasiga javob berilgan."}
        </div>
      ) : (
        <div className="signalList">
          {events.map((event) => {
            const payload = event.payload || {};
            const risk = (payload.risk_level || "").toLowerCase();
            const answered = event.work_status === "answered";
            return (
              <article className={`signalRow ${risk}`} key={event.id}>
                <div className="signalMeta">
                  <span className={`signalRisk ${risk || "low"}`}>{riskLabels[risk] || risk || "-"}</span>
                  <strong>{payload.source || "-"}</strong>
                  <span className="signalDim">{platformLabels[payload.platform] || payload.platform}</span>
                  <span className="signalDim">· {payload.author || "-"}</span>
                  <span className="signalDim">· {answered ? `yopildi: ${event.answered_by}` : `${waitedText(event.created_at)} kutmoqda`}</span>
                </div>
                <p className="signalText">{payload.text || payload.summary || ""}</p>
                {payload.suggested_action && <p className="signalAction">Tavsiya: {payload.suggested_action}</p>}
                <div className="signalFooter">
                  {event.checked_by && !answered && <span className="signalDim">👀 Tekshirgan: {event.checked_by}</span>}
                  {answered && <span className="signalDim">🔎 {event.checked_by} · ✅ {event.answered_by}</span>}
                  <div className="signalActions">
                    {payload.permalink && (
                      <a className="button secondary" href={payload.permalink} target="_blank" rel="noreferrer">
                        <ExternalLink size={16} />
                        <span>Kommentga o'tish</span>
                      </a>
                    )}
                    {answered ? (
                      <button className="button secondary" type="button" disabled={busyId === event.id} onClick={() => act(event.id, "reopen")}>
                        <RotateCcw size={16} />
                        <span>Qayta ochish</span>
                      </button>
                    ) : (
                      <>
                        {event.work_status !== "checked" && (
                          <button className="button secondary" type="button" disabled={busyId === event.id} onClick={() => act(event.id, "check")}>
                            <Eye size={16} />
                            <span>Tekshirildi</span>
                          </button>
                        )}
                        <button className="button" type="button" disabled={busyId === event.id} onClick={() => act(event.id, "answer")}>
                          <CheckCheck size={16} />
                          <span>Javob berdim</span>
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

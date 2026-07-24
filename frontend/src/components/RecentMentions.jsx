import {
  AlertTriangle,
  CheckCircle2,
  MessageSquareText,
  MinusCircle,
  ShieldAlert,
  ThumbsDown,
  ThumbsUp,
  X,
} from "lucide-react";
import { useState } from "react";
import { formatUiDate } from "../i18n";

const sourceTypeLabels = {
  channel_post: "Kanal posti",
  comment: "Discuss comment",
  group_message: "Guruh xabari",
  message: "Bot/private xabar",
};

const mediaTypeLabels = {
  photo: "Rasm",
  video: "Video",
  audio: "Audio",
  voice: "Voice",
  document: "Fayl",
  animation: "GIF",
  sticker: "Sticker",
  poll: "So'rovnoma",
  MessageMediaPhoto: "Rasm",
  MessageMediaDocument: "Fayl/media",
  MessageMediaPoll: "So'rovnoma",
  MessageMediaWebPage: "Link preview",
  MessageMediaContact: "Kontakt",
  MessageMediaGeo: "Lokatsiya",
  MessageMediaVenue: "Manzil",
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

function sourceLabel(mention) {
  if (mention.chat_username) return `@${mention.chat_username}`;
  return mention.chat_title || String(mention.chat_id);
}

function mentionText(mention) {
  return mention.text || mention.caption || "";
}

function formatDate(value) {
  if (!value) return "";
  return formatUiDate(value, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

function sourceTypeLabel(value) {
  return sourceTypeLabels[value] || value || "Xabar";
}

function mediaTypeLabel(value) {
  return mediaTypeLabels[value] || value;
}

function SentimentIcon({ sentiment }) {
  if (sentiment === "positive") return <ThumbsUp size={11} aria-hidden="true" />;
  if (sentiment === "negative") return <ThumbsDown size={11} aria-hidden="true" />;
  if (sentiment === "mixed") return <AlertTriangle size={11} aria-hidden="true" />;
  return <MinusCircle size={11} aria-hidden="true" />;
}

function RiskIcon({ level }) {
  if (level === "critical" || level === "high") return <ShieldAlert size={11} aria-hidden="true" />;
  if (level === "medium") return <AlertTriangle size={11} aria-hidden="true" />;
  return <CheckCircle2 size={11} aria-hidden="true" />;
}

export function RecentMentions({ mentions, loading = false }) {
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
              <h2>Oxirgi mentionlar</h2>
              <p>Telegram post, comment va bot message oqimi.</p>
            </>
          )}
        </div>
      </div>

      <div className="mentionList">
        {loading ? (
          Array.from({ length: 7 }).map((_, index) => (
            <div className="mentionItem skeletonMention" key={`mention-skeleton-${index}`}>
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
                <MessageSquareText size={18} />
              </div>
              <div className="mentionBody">
                <strong>{sourceLabel(mention)}</strong>
                {mentionText(mention)
                  ? <p data-i18n-ignore="true">{mentionText(mention)}</p>
                  : <p>Matn yo'q</p>}
                <div className="mentionBadgeRow">
                  {mention.media_type && <span>{mediaTypeLabel(mention.media_type)}</span>}
                  {!!mention.brand_match_terms?.length && <span className="warning">Brand signal</span>}
                </div>
                {mention.analysis && !mention.analysis.error ? (
                  <div className="mentionAnalysis">
                    <div className="mentionBadgeRow">
                      {mention.analysis.sentiment && (
                        <span className={`sentimentBadge ${mention.analysis.sentiment}`}>
                          <SentimentIcon sentiment={mention.analysis.sentiment} />
                          {sentimentLabels[mention.analysis.sentiment] || mention.analysis.sentiment}
                          {typeof mention.analysis.sentiment_score === "number"
                            ? ` · ${mention.analysis.sentiment_score.toFixed(2)}`
                            : ""}
                        </span>
                      )}
                      {mention.analysis.risk_level && (
                        <span className={`riskBadge ${mention.analysis.risk_level}`}>
                          <RiskIcon level={mention.analysis.risk_level} />
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
                <em title={mention.source_type}>{sourceTypeLabel(mention.source_type)}</em>
                <small title="Xabar Telegramda yozilgan vaqt">{formatDate(mention.message_date)}</small>
              </span>
            </button>
          ))
        ) : (
          <div className="empty">Mention yo'q</div>
        )}
      </div>

      {selectedMention && (
        <div className="modalOverlay" role="presentation" onMouseDown={() => setSelectedMention(null)}>
          <section
            className="modalPanel mentionModal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="mention-detail-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="modalHeader">
              <div>
                <h2 id="mention-detail-title">{sourceLabel(selectedMention)}</h2>
                <p>
                  {sourceTypeLabel(selectedMention.source_type)} · {formatDate(selectedMention.message_date)}
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
                    <span className="mentionSignal" key={term}>
                      {term}
                    </span>
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
            </div>
          </section>
        </div>
      )}
    </section>
  );
}

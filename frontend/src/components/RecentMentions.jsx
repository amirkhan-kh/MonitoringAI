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
import { useMemo, useState } from "react";
import { formatUiDate, translateUiText, useUiLanguage } from "../i18n";

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
  if (mention.chat_title) return mention.chat_title;
  if (mention.author_username) return `@${String(mention.author_username).replace(/^@/, "")}`;
  if (mention.author_name) return mention.author_name;
  if (mention.channel_title) return mention.channel_title;
  if (mention.video_title) return mention.video_title;
  if (mention.page_name) return mention.page_name;
  if (mention.chat_id != null) return String(mention.chat_id);
  return "Mention";
}

function mentionText(mention) {
  return mention.text || mention.caption || mention.title || "";
}

function mentionDate(mention) {
  return mention.message_date || mention.published_at || mention.created_at || mention.timestamp;
}

function formatDate(value) {
  if (!value) return "";
  return formatUiDate(value, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

function sourceTypeLabel(value, lng) {
  const key = sourceTypeLabels[value] || value || "Xabar";
  return translateUiText(key, { lng });
}

function mediaTypeLabel(value, lng) {
  const key = mediaTypeLabels[value] || value;
  return key ? translateUiText(key, { lng }) : key;
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

/** Filter mentions by AI analysis sentiment (positive = maqtov, negative = shikoyat). */
export function filterMentionsBySentiment(mentions = [], sentiment) {
  if (!sentiment) return mentions || [];
  return (mentions || []).filter(
    (mention) => mention?.analysis && !mention.analysis.error && mention.analysis.sentiment === sentiment,
  );
}

/**
 * Shared mention stream card used on monitoring pages.
 * @param {string|null} sentimentFilter - null | "positive" | "negative"
 */
export function RecentMentions({
  mentions = [],
  loading = false,
  title = "Oxirgi mentionlar",
  description = "Post, comment va bot oqimi.",
  emptyText = "Mention yo'q",
  sentimentFilter = null,
}) {
  const lng = useUiLanguage();
  const tt = (value) => translateUiText(value, { lng });
  const [selectedMention, setSelectedMention] = useState(null);
  const rows = useMemo(
    () => filterMentionsBySentiment(mentions, sentimentFilter),
    [mentions, sentimentFilter],
  );

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
              <h2 data-i18n-ignore="true">{tt(title)}</h2>
              <p data-i18n-ignore="true">{tt(description)}</p>
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
        ) : rows.length ? (
          rows.map((mention) => (
            <button className="mentionItem" type="button" key={mention.id} onClick={() => setSelectedMention(mention)}>
              <div className="mentionIcon">
                <MessageSquareText size={18} />
              </div>
              <div className="mentionBody">
                <strong>{sourceLabel(mention)}</strong>
                {mentionText(mention)
                  ? <p data-i18n-ignore="true">{mentionText(mention)}</p>
                  : <p data-i18n-ignore="true">{tt("Matn yo'q")}</p>}
                <div className="mentionBadgeRow">
                  {mention.media_type && (
                    <span data-i18n-ignore="true">{mediaTypeLabel(mention.media_type, lng)}</span>
                  )}
                  {!!mention.brand_match_terms?.length && (
                    <span className="warning" data-i18n-ignore="true">{tt("Brand signal")}</span>
                  )}
                </div>
                {mention.analysis && !mention.analysis.error ? (
                  <div className="mentionAnalysis">
                    <div className="mentionBadgeRow">
                      {mention.analysis.sentiment && (
                        <span className={`sentimentBadge ${mention.analysis.sentiment}`} data-i18n-ignore="true">
                          <SentimentIcon sentiment={mention.analysis.sentiment} />
                          {tt(sentimentLabels[mention.analysis.sentiment] || mention.analysis.sentiment)}
                          {typeof mention.analysis.sentiment_score === "number"
                            ? ` · ${mention.analysis.sentiment_score.toFixed(2)}`
                            : ""}
                        </span>
                      )}
                      {mention.analysis.risk_level && (
                        <span className={`riskBadge ${mention.analysis.risk_level}`} data-i18n-ignore="true">
                          <RiskIcon level={mention.analysis.risk_level} />
                          {tt(riskLabels[mention.analysis.risk_level] || mention.analysis.risk_level)}
                        </span>
                      )}
                    </div>
                    {mention.analysis.summary && (
                      <p className="mentionSummary" data-i18n-ignore="true">{mention.analysis.summary}</p>
                    )}
                    {mention.analysis.suggested_action && (
                      <p className="mentionAction" data-i18n-ignore="true">{mention.analysis.suggested_action}</p>
                    )}
                  </div>
                ) : (
                  <span className="mentionPending" data-i18n-ignore="true">{tt("AI tahlil kutilmoqda…")}</span>
                )}
              </div>
              <span className="mentionMeta">
                <em title={mention.source_type || mention.item_type} data-i18n-ignore="true">
                  {sourceTypeLabel(mention.source_type || mention.item_type, lng)}
                </em>
                <small title={tt("Mention vaqti")}>{formatDate(mentionDate(mention))}</small>
              </span>
            </button>
          ))
        ) : (
          <div className="empty" data-i18n-ignore="true">{tt(emptyText)}</div>
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
                <p data-i18n-ignore="true">
                  {sourceTypeLabel(selectedMention.source_type || selectedMention.item_type, lng)} ·{" "}
                  {formatDate(mentionDate(selectedMention))}
                </p>
              </div>
              <button
                className="iconButton"
                type="button"
                aria-label={tt("Yopish")}
                onClick={() => setSelectedMention(null)}
              >
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
                : <p data-i18n-ignore="true">{tt("Bu mentionda matn topilmadi.")}</p>}
              {selectedMention.analysis && !selectedMention.analysis.error && (
                <div className="mentionAnalysis modalAnalysis">
                  <div className="mentionBadgeRow">
                    {selectedMention.analysis.sentiment && (
                      <span className={`sentimentBadge ${selectedMention.analysis.sentiment}`} data-i18n-ignore="true">
                        {tt(sentimentLabels[selectedMention.analysis.sentiment] || selectedMention.analysis.sentiment)}
                      </span>
                    )}
                    {selectedMention.analysis.risk_level && (
                      <span className={`riskBadge ${selectedMention.analysis.risk_level}`} data-i18n-ignore="true">
                        {tt(riskLabels[selectedMention.analysis.risk_level] || selectedMention.analysis.risk_level)}
                      </span>
                    )}
                  </div>
                  {selectedMention.analysis.summary && (
                    <p className="mentionSummary" data-i18n-ignore="true">{selectedMention.analysis.summary}</p>
                  )}
                  {selectedMention.analysis.suggested_action && (
                    <p className="mentionAction" data-i18n-ignore="true">{selectedMention.analysis.suggested_action}</p>
                  )}
                </div>
              )}
            </div>
          </section>
        </div>
      )}
    </section>
  );
}

/** Pair of analysis-filtered mention panels for any monitoring page. */
export function MentionsAnalysisPanels({ mentions = [], loading = false, platformLabel = "" }) {
  const lng = useUiLanguage();
  const tt = (value) => translateUiText(value, { lng });
  const platform = platformLabel ? translateUiText(platformLabel, { lng }) : "";
  const positiveDesc = platform
    ? `${tt("AI tahlilidan ijobiy mentionlar")} · ${platform}`
    : tt("AI tahlilidan ijobiy mentionlar");
  const negativeDesc = platform
    ? `${tt("AI tahlilidan salbiy mentionlar")} · ${platform}`
    : tt("AI tahlilidan salbiy mentionlar");
  return (
    <section
      className="mentionsAnalysisGrid"
      aria-label={tt("AI tahlil bo'yicha maqtov va shikoyat")}
    >
      <RecentMentions
        mentions={mentions}
        loading={loading}
        sentimentFilter="positive"
        title="Maqtovlar"
        description={positiveDesc}
        emptyText="Maqtov topilmadi"
      />
      <RecentMentions
        mentions={mentions}
        loading={loading}
        sentimentFilter="negative"
        title="Shikoyatlar"
        description={negativeDesc}
        emptyText="Shikoyat topilmadi"
      />
    </section>
  );
}

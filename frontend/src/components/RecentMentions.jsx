import { MessageSquareText, X } from "lucide-react";
import { useState } from "react";

const monthNames = [
  "yanvar",
  "fevral",
  "mart",
  "aprel",
  "may",
  "iyun",
  "iyul",
  "avgust",
  "sentabr",
  "oktabr",
  "noyabr",
  "dekabr",
];

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

function sourceLabel(mention) {
  if (mention.chat_username) return `@${mention.chat_username}`;
  return mention.chat_title || String(mention.chat_id);
}

function mentionText(mention) {
  return mention.text || mention.caption || "";
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  const day = String(date.getDate()).padStart(2, "0");
  const month = monthNames[date.getMonth()];
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");
  return `${day}-${month} ${hour}:${minute}`;
}

function sourceTypeLabel(value) {
  return sourceTypeLabels[value] || value || "Xabar";
}

function mediaTypeLabel(value) {
  return mediaTypeLabels[value] || value;
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
                <p>{mentionText(mention) || "Matn yo'q"}</p>
                <div className="mentionBadgeRow">
                  {mention.media_type && <span>{mediaTypeLabel(mention.media_type)}</span>}
                  {!!mention.brand_match_terms?.length && <span className="warning">Brand signal</span>}
                </div>
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
              <p>{mentionText(selectedMention) || "Bu mentionda matn topilmadi."}</p>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}

import { AlertTriangle, Archive, Trash2, X } from "lucide-react";

/**
 * Asks what should happen to a source's already analysed mentions before removing it.
 *
 * Deleting a source is often a slip, and the mentions behind it are expensive: each one
 * already cost an AI analysis and feeds the brand's statistics. So the destructive path
 * is never the default — the operator picks "keep" (source goes, mentions stay, re-adding
 * the source later resumes without re-analysing anything) or "purge" (everything goes,
 * freeing server space) explicitly.
 *
 * Every label below is a whole sentence in its own text node so the i18n MutationObserver
 * can swap it for the ru/en translation; interpolated values stay outside those nodes.
 */
export default function DeleteSourceModal({ open, sourceName, busy, onCancel, onConfirm }) {
  if (!open) return null;

  return (
    <div className="modalOverlay" role="presentation" onMouseDown={busy ? undefined : onCancel}>
      <section
        className="modalPanel deleteSourceModal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-source-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="modalHeader">
          <div>
            <h2 id="delete-source-title">
              <AlertTriangle size={18} className="deleteSourceModalIcon" aria-hidden="true" />
              <span>Source o'chirilsinmi?</span>
            </h2>
            <p className="deleteSourceName">{sourceName}</p>
            <p>Bu manbadan yig'ilgan va AI tahlil qilingan mentionlar bilan nima qilishni tanlang.</p>
          </div>
          <button className="iconButton" type="button" aria-label="Yopish" onClick={onCancel} disabled={busy}>
            <X size={18} />
          </button>
        </div>

        <div className="modalContent deleteSourceChoices">
          <button className="deleteSourceChoice keep" type="button" onClick={() => onConfirm(false)} disabled={busy}>
            <Archive size={20} aria-hidden="true" />
            <span className="deleteSourceChoiceBody">
              <span className="deleteSourceChoiceTitle">Mentionlar saqlansin</span>
              <span className="deleteSourceChoiceHint">
                Faqat source o'chadi, tahlil qilingan mentionlar brand statistikasida qoladi. Behosdan o'chirgan
                bo'lsangiz shuni tanlang: bu manbani qayta ulaganingizda uzilish davridagi tahlil qilinmagan
                xabarlargina tahlil qilinadi, eskilari qayta tahlil qilinmaydi.
              </span>
            </span>
          </button>

          <button className="deleteSourceChoice purge" type="button" onClick={() => onConfirm(true)} disabled={busy}>
            <Trash2 size={20} aria-hidden="true" />
            <span className="deleteSourceChoiceBody">
              <span className="deleteSourceChoiceTitle">Mentionlar ham o'chirilsin</span>
              <span className="deleteSourceChoiceHint">
                Source bilan birga barcha post, comment, AI tahlil va alertlar butunlay o'chadi va serverda joy
                bo'shaydi. Brand statistikasi o'zgaradi va bu amalni ortga qaytarib bo'lmaydi.
              </span>
            </span>
          </button>
        </div>

        <div className="deleteSourceFooter">
          <button className="button secondary" type="button" onClick={onCancel} disabled={busy}>
            Bekor qilish
          </button>
        </div>
      </section>
    </div>
  );
}

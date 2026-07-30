import {
  Eye,
  EyeOff,
  Instagram,
  Facebook,
  PlayCircle,
  Plus,
  ShieldAlert,
  CheckCircle2,
} from "lucide-react";
import { useState } from "react";
import MetaConnectGuideModal from "./MetaConnectGuideModal.jsx";
import { translateUiText } from "../i18n";

/**
 * Shared Instagram / Facebook connect form for the add-source modal
 * (mirrors TelegramConnectionForm layout: brand, identity, token, guide CTA).
 */
export function MetaConnectForm({
  platform = "instagram",
  brands = [],
  selectedBrandId = "",
  selectedBrandName = "",
  form,
  onChange,
  onSubmit,
  submitting = false,
  onOauth = null,
  oauthBusy = false,
}) {
  const isInstagram = platform === "instagram";
  const [showToken, setShowToken] = useState(false);
  const [guideOpen, setGuideOpen] = useState(false);
  const [validationError, setValidationError] = useState("");

  const identityLabel = isInstagram ? "Instagram username" : "Facebook Page nomi";
  const identityPlaceholder = isInstagram ? "brand_nomi yoki @brand_nomi" : "Brand Page";
  const identityHint = isInstagram
    ? "Ixtiyoriy. Token to'g'ri bo'lsa profil avtomatik aniqlanadi."
    : "Ixtiyoriy. Token to'g'ri bo'lsa sahifa avtomatik aniqlanadi.";
  const submitLabel = isInstagram ? "Akkauntni ulash" : "Sahifani ulash";
  const guideLinkLabel = isInstagram
    ? "Username va token olish qo'llanmasini ko'rish"
    : "Page va token olish qo'llanmasini ko'rish";

  function handleField(key, value) {
    onChange?.({ ...form, [key]: value });
  }

  function handleBrand(value) {
    onChange?.({ ...form, brand_id: value });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!form.brand_id) {
      setValidationError("Avval brandni tanlang.");
      return;
    }
    if (!String(form.access_token || "").trim()) {
      setValidationError("Access token majburiy.");
      return;
    }
    setValidationError("");
    await onSubmit?.(event);
  }

  const PlatformIcon = isInstagram ? Instagram : Facebook;

  return (
    <>
      <form className="sourceForm telegramConnectionForm metaConnectForm" onSubmit={handleSubmit}>
        <div className={`telegramSelectedBrand full ${form.brand_id || selectedBrandId ? "ready" : "missing"}`}>
          {form.brand_id || selectedBrandId ? <CheckCircle2 size={17} /> : <ShieldAlert size={17} />}
          <div>
            <span>Tanlangan brand</span>
            <strong>
              {selectedBrandName
                || brands.find((b) => b.id === (form.brand_id || selectedBrandId))?.name
                || form.brand_id
                || selectedBrandId
                || "Brand tanlanmagan"}
            </strong>
          </div>
        </div>

        <div className="telegramConnectorInputs full">
          <section className="telegramConnectorInputCard channel">
            <div className="telegramConnectorInputHead">
              <span className="telegramConnectorStepBadge" aria-hidden="true">1</span>
              <PlatformIcon size={18} />
              <div>
                <strong>{isInstagram ? "Instagram akkaunt" : "Facebook Page"}</strong>
                <span>{isInstagram ? "Business / Creator" : "Page access token"}</span>
              </div>
            </div>

            <label className="field">
              <span>Brand</span>
              <select
                className="input select"
                value={form.brand_id || ""}
                onChange={(event) => handleBrand(event.target.value)}
                required
              >
                <option value="">{translateUiText("Brand tanlang")}</option>
                {brands.map((brand) => (
                  <option key={brand.id} value={brand.id}>{brand.name}</option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>{identityLabel}</span>
              <input
                className="input"
                value={isInstagram ? (form.username || "") : (form.page_name || "")}
                onChange={(event) => handleField(isInstagram ? "username" : "page_name", event.target.value)}
                placeholder={identityPlaceholder}
                autoComplete="off"
                spellCheck="false"
              />
              <p className="fieldHint">{identityHint}</p>
            </label>

            <label className="field">
              <span>Access token</span>
              <div className="tokenInputWrap">
                <input
                  className="input"
                  type={showToken ? "text" : "password"}
                  value={form.access_token || ""}
                  onChange={(event) => handleField("access_token", event.target.value)}
                  placeholder={isInstagram ? "IGQVJ… yoki EAAG…" : "EAAG…"}
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

            <button className="telegramBotGuideLink" type="button" onClick={() => setGuideOpen(true)}>
              <PlayCircle size={16} aria-hidden="true" />
              <span>{guideLinkLabel}</span>
            </button>
          </section>
        </div>

        {isInstagram && onOauth && (
          <div className="igOauthCard full metaConnectOauth">
            <div className="igOauthText">
              <strong>Instagram bilan ulanish</strong>
              <span>
                Meta rasmiy oynasida ruxsat — token qo'lda nusxalanmaydi, 60 kunlik token avtomatik olinadi.
              </span>
            </div>
            <button
              className="button secondary"
              type="button"
              disabled={oauthBusy || !form.brand_id}
              onClick={onOauth}
            >
              <Instagram size={17} />
              <span>{oauthBusy ? "Yo'naltirilmoqda..." : "OAuth orqali ulash"}</span>
            </button>
          </div>
        )}

        {validationError && (
          <div className="backfillResult bad full">
            <ShieldAlert size={16} />
            <span>{validationError}</span>
          </div>
        )}

        <div className="buttonRow profileModalActions full">
          <button className="button primary" type="submit" disabled={submitting || !form.brand_id}>
            <Plus size={17} />
            <span>{submitting ? "Ulanmoqda..." : submitLabel}</span>
          </button>
        </div>
      </form>

      <MetaConnectGuideModal
        open={guideOpen}
        platform={platform}
        onClose={() => setGuideOpen(false)}
      />
    </>
  );
}

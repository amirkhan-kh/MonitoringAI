import { ArrowLeft, Check, Copy, Pause, Play, RotateCcw, Search, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Instagram / Facebook connect walkthrough — same phone-simulator UX as BotFatherGuideModal.
 * Scripted DOM animation (no mp4/gif): crisp, i18n-friendly captions, light bundle.
 */

const DEMO = {
  instagram: {
    username: "brand_profili",
    displayName: "Brand Profili",
    token: "IGQVJYx0mNbR4sTuVwXyZaBcDeFgH…",
    tokenFull: "IGQVJYx0mNbR4sTuVwXyZaBcDeFgH9k2LpQvJx0mN",
    fieldLabel: "Instagram username",
    tokenLabel: "Access token",
    pasteTitle: "MonitoringAI — Instagram",
    pasteDone: "Akkaunt ulanishga tayyor",
    guideTitle: "Instagram ulash qo'llanmasi",
    guideSubtitle: "Ikki qisqa ko'rsatma: username qayerdan olinadi va Meta'dan token qanday olinadi.",
    footnote:
      "Token parol bilan teng: uni hech kimga bermang. Leak bo'lsa Meta Developer App'da tokenni revoke qilib yangisini oling.",
  },
  facebook: {
    username: "Brand Page",
    displayName: "Brand Page",
    token: "EAAG9k2LpQvJx0mNbR4sTuVw…",
    tokenFull: "EAAG9k2LpQvJx0mNbR4sTuVwXyZaBcDeFgH",
    fieldLabel: "Facebook Page nomi",
    tokenLabel: "Access token",
    pasteTitle: "MonitoringAI — Facebook",
    pasteDone: "Sahifa ulanishga tayyor",
    guideTitle: "Facebook Page ulash qo'llanmasi",
    guideSubtitle: "Ikki qisqa ko'rsatma: Page qayerdan topiladi va Business Manager / Developers'dan token qanday olinadi.",
    footnote:
      "Page token parol bilan teng. Leak bo'lsa System User → Generate new token orqali yangilang va eskisini revoke qiling.",
  },
};

function typed(text, time, from, to) {
  if (time <= from) return "";
  if (time >= to) return text;
  return text.slice(0, Math.round((text.length * (time - from)) / (to - from)));
}

function ramp(time, from, to) {
  if (time <= from) return 0;
  if (time >= to) return 1;
  const progress = (time - from) / (to - from);
  return progress < 0.5
    ? 2 * progress * progress
    : 1 - ((-2 * progress + 2) ** 2) / 2;
}

function lerp(from, to, progress) {
  return from + (to - from) * progress;
}

function useTimeline(duration, playing, resetKey, onEnd) {
  const [time, setTime] = useState(0);
  const timeRef = useRef(0);

  useEffect(() => {
    timeRef.current = 0;
    setTime(0);
  }, [resetKey]);

  useEffect(() => {
    if (!playing) return undefined;
    let frame = 0;
    const origin = performance.now() - timeRef.current * 1000;
    const tick = (now) => {
      const elapsed = Math.min(duration, (now - origin) / 1000);
      timeRef.current = elapsed;
      setTime(elapsed);
      if (elapsed >= duration) {
        onEnd?.();
        return;
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, duration, onEnd, resetKey]);

  return time;
}

function prefersReducedMotion() {
  return typeof window !== "undefined"
    && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}

function PhoneChrome({ platform, title, subtitle, children, composer }) {
  const avatar = platform === "facebook" ? "f" : "IG";
  return (
    <div className={`botGuidePhone metaGuidePhone ${platform}`}>
      <div className="botGuidePhoneNotch" aria-hidden="true" />
      <div className="botGuideStatusBar" aria-hidden="true">
        <span>9:41</span>
        <span className="botGuideStatusIcons">
          <i className="botGuideSignal" />
          <i className="botGuideWifi" />
          <i className="botGuideBattery" />
        </span>
      </div>
      <div className={`botGuideAppBar metaGuideAppBar ${platform}`}>
        <ArrowLeft size={17} aria-hidden="true" />
        <span className={`botGuideAppAvatar metaGuideAvatar ${platform}`} aria-hidden="true">{avatar}</span>
        <span className="botGuideAppTitle">
          <strong>{title}</strong>
          <em>{subtitle}</em>
        </span>
      </div>
      <div className="botGuideScreen">{children}</div>
      {composer}
    </div>
  );
}

function Fingertip({ x, y, visible, pressing }) {
  if (!visible) return null;
  return (
    <span
      className={`botGuideFinger ${pressing ? "pressing" : ""}`}
      style={{ left: `${x}%`, top: `${y}%` }}
      aria-hidden="true"
    />
  );
}

/* ------------------------------------------------------------------ */
/* Instagram scene 1 — find @username on profile                       */
/* ------------------------------------------------------------------ */

const IG_SCENE_ONE_STEPS = [
  { at: 0, label: "Instagram ilovasini oching" },
  { at: 1.8, label: "Pastki o'ngdagi profil ikonkasini bosing" },
  { at: 3.6, label: "Profil boshida @username ko'rinadi" },
  { at: 5.4, label: "Username'ni eslab qoling yoki nusxalang" },
  { at: 7.4, label: "Business / Creator akkaunt bo'lishi kerak" },
  { at: 9.0, label: "Username tayyor — token olishga o'ting" },
];

function InstagramSceneOne({ time }) {
  const onHome = time < 2.4;
  const highlightUser = time >= 3.8;
  const copying = time >= 5.6 && time < 7.0;
  const demo = DEMO.instagram;

  if (onHome) {
    return (
      <PhoneChrome platform="instagram" title="Instagram" subtitle="feed">
        <div className="metaGuideIgHome">
          <div className="metaGuideIgStories">
            {["Siz", "Meta", "Ads"].map((label) => (
              <span key={label} className="metaGuideIgStory">
                <i />
                <em>{label}</em>
              </span>
            ))}
          </div>
          <div className="metaGuideIgPost">
            <strong>meta</strong>
            <span className="metaGuideIgPostBody" />
          </div>
          <div className="metaGuideIgTabBar">
            <span />
            <span />
            <span />
            <span />
            <span className={time > 1.9 ? "active" : ""} />
          </div>
        </div>
        <Fingertip
          x={lerp(50, 88, ramp(time, 1.5, 2.2))}
          y={lerp(50, 92, ramp(time, 1.5, 2.2))}
          visible={time > 1.4}
          pressing={time > 2.1}
        />
      </PhoneChrome>
    );
  }

  return (
    <PhoneChrome platform="instagram" title="Profil" subtitle="instagram.com">
      <div className="metaGuideIgProfile">
        <div className="metaGuideIgProfileHead">
          <span className="metaGuideIgAvatar" />
          <div>
            <strong className={highlightUser ? "metaGuideHighlight" : ""}>
              @{demo.username}
              {copying && (
                <span className="botGuideCopyMenu">
                  <Copy size={11} aria-hidden="true" />
                  <span>Copy</span>
                </span>
              )}
            </strong>
            <em>{demo.displayName}</em>
            <span className="metaGuideBadge">Professional · Business</span>
          </div>
        </div>
        <div className="metaGuideIgStats">
          <span><b>128</b> posts</span>
          <span><b>12.4K</b> followers</span>
          <span><b>210</b> following</span>
        </div>
        <div className="metaGuideIgGrid">
          {Array.from({ length: 6 }).map((_, index) => (
            <i key={index} />
          ))}
        </div>
      </div>
      <Fingertip
        x={lerp(70, 42, ramp(time, 5.2, 5.8))}
        y={lerp(88, 28, ramp(time, 5.2, 5.8))}
        visible={time > 5.1 && time < 7.1}
        pressing={copying}
      />
    </PhoneChrome>
  );
}

/* ------------------------------------------------------------------ */
/* Instagram scene 2 — token from Meta Developers / Graph Explorer     */
/* ------------------------------------------------------------------ */

const IG_SCENE_TWO_STEPS = [
  { at: 0, label: "developers.facebook.com ni oching" },
  { at: 1.6, label: "App → Tools → Graph API Explorer" },
  { at: 3.4, label: "User/Page token yarating (IG ruxsatlari bilan)" },
  { at: 5.2, label: "Access Token maydonidan nusxa oling" },
  { at: 7.2, label: "Username va tokenni MonitoringAI ga joylang" },
  { at: 9.0, label: "«Akkauntni ulash» — tayyor" },
];

function InstagramSceneTwo({ time }) {
  const demo = DEMO.instagram;
  const generating = time >= 3.5 && time < 5.0;
  const copying = time >= 5.4 && time < 7.0;
  const tokenVisible = time >= 4.2;
  const tokenText = tokenVisible
    ? typed(demo.tokenFull, time, 4.2, 5.1)
    : "";

  return (
    <PhoneChrome platform="instagram" title="Meta Developers" subtitle="Graph API Explorer">
      <div className="metaGuideDev">
        <div className="metaGuideDevTop">
          <Search size={12} aria-hidden="true" />
          <span>developers.facebook.com/tools/explorer</span>
        </div>
        <div className="metaGuideDevBody">
          <label className="metaGuideDevField">
            <span>Meta App</span>
            <em>MonitoringAI App</em>
          </label>
          <label className="metaGuideDevField">
            <span>User or Page</span>
            <em>Instagram Business · @{demo.username}</em>
          </label>
          <div className="metaGuidePerms">
            <span>instagram_basic</span>
            <span>instagram_manage_comments</span>
            <span>pages_show_list</span>
          </div>
          <button
            className={`metaGuideGenerate ${generating ? "active" : ""}`}
            type="button"
            tabIndex={-1}
          >
            Generate Access Token
          </button>
          <label className={`metaGuideDevField token ${copying ? "active" : ""}`}>
            <span>Access Token</span>
            <em className="mono">
              {tokenText || "••••••••••••"}
              {copying && (
                <span className="botGuideCopyMenu">
                  {time > 6.4 ? <Check size={11} /> : <Copy size={11} />}
                  <span>{time > 6.4 ? "Copied" : "Copy"}</span>
                </span>
              )}
            </em>
          </label>
        </div>
      </div>
      <Fingertip
        x={lerp(78, 52, ramp(time, 5.0, 5.6))}
        y={lerp(88, 72, ramp(time, 5.0, 5.6))}
        visible={time > 4.9 && time < 7.0}
        pressing={copying}
      />
    </PhoneChrome>
  );
}

/* ------------------------------------------------------------------ */
/* Facebook scene 1 — find Page name                                   */
/* ------------------------------------------------------------------ */

const FB_SCENE_ONE_STEPS = [
  { at: 0, label: "Facebook yoki Meta Business Suite oching" },
  { at: 1.8, label: "Pages (Sahifalar) bo'limiga o'ting" },
  { at: 3.6, label: "Monitoring qilmoqchi bo'lgan Page'ni tanlang" },
  { at: 5.4, label: "Page nomini eslab qoling" },
  { at: 7.2, label: "Sizda Page uchun Full control bo'lishi kerak" },
  { at: 9.0, label: "Page nomi tayyor — token olishga o'ting" },
];

function FacebookSceneOne({ time }) {
  const demo = DEMO.facebook;
  const onList = time < 3.5;
  const highlight = time >= 5.2;
  const copying = time >= 5.8 && time < 7.2;

  if (onList) {
    return (
      <PhoneChrome platform="facebook" title="Meta Business" subtitle="Pages">
        <div className="metaGuideFbPages">
          <div className="metaGuideDevTop">
            <Search size={12} aria-hidden="true" />
            <span>business.facebook.com · Pages</span>
          </div>
          {["Brand Page", "Support Page", "HR Page"].map((name, index) => (
            <div
              key={name}
              className={`metaGuideFbPageRow ${index === 0 && time > 2.8 ? "tapped" : ""}`}
            >
              <span className="metaGuideFbPageIcon">f</span>
              <span>
                <strong>{name}</strong>
                <em>{index === 0 ? "Connected · Full control" : "Viewer"}</em>
              </span>
            </div>
          ))}
        </div>
        <Fingertip
          x={lerp(70, 40, ramp(time, 2.4, 3.0))}
          y={lerp(88, 38, ramp(time, 2.4, 3.0))}
          visible={time > 2.3}
          pressing={time > 2.9}
        />
      </PhoneChrome>
    );
  }

  return (
    <PhoneChrome platform="facebook" title="Page" subtitle="Brand Page">
      <div className="metaGuideFbPageDetail">
        <span className="metaGuideFbCover" />
        <div className="metaGuideFbPageHead">
          <span className="metaGuideFbPageIcon large">f</span>
          <div>
            <strong className={highlight ? "metaGuideHighlight" : ""}>
              {demo.displayName}
              {copying && (
                <span className="botGuideCopyMenu">
                  <Copy size={11} />
                  <span>Copy</span>
                </span>
              )}
            </strong>
            <em>Facebook Page · Public</em>
          </div>
        </div>
        <div className="metaGuideFbMeta">
          <span>12.4K like</span>
          <span>Full control</span>
        </div>
      </div>
      <Fingertip
        x={lerp(70, 38, ramp(time, 5.4, 6.0))}
        y={lerp(88, 42, ramp(time, 5.4, 6.0))}
        visible={time > 5.3 && time < 7.2}
        pressing={copying}
      />
    </PhoneChrome>
  );
}

/* ------------------------------------------------------------------ */
/* Facebook scene 2 — System User token                                */
/* ------------------------------------------------------------------ */

const FB_SCENE_TWO_STEPS = [
  { at: 0, label: "business.facebook.com/settings oching" },
  { at: 1.6, label: "Users → System users → Add" },
  { at: 3.4, label: "Page'ni Assign assets (Full control)" },
  { at: 5.2, label: "Generate new token → kerakli permissions" },
  { at: 7.2, label: "Token va Page nomini MonitoringAI ga joylang" },
  { at: 9.0, label: "«Sahifani ulash» — tayyor" },
];

function FacebookSceneTwo({ time }) {
  const demo = DEMO.facebook;
  const generating = time >= 3.6 && time < 5.2;
  const copying = time >= 5.6 && time < 7.1;
  const tokenText = time >= 4.4
    ? typed(demo.tokenFull, time, 4.4, 5.3)
    : "";

  return (
    <PhoneChrome platform="facebook" title="Business Settings" subtitle="System users">
      <div className="metaGuideDev">
        <div className="metaGuideDevTop">
          <Search size={12} aria-hidden="true" />
          <span>business.facebook.com/settings</span>
        </div>
        <div className="metaGuideDevBody">
          <label className="metaGuideDevField">
            <span>System user</span>
            <em>monitoring_bot</em>
          </label>
          <label className="metaGuideDevField">
            <span>Assigned asset</span>
            <em>{demo.displayName} · Full control</em>
          </label>
          <div className="metaGuidePerms">
            <span>pages_show_list</span>
            <span>pages_read_engagement</span>
            <span>pages_read_user_content</span>
          </div>
          <button
            className={`metaGuideGenerate fb ${generating ? "active" : ""}`}
            type="button"
            tabIndex={-1}
          >
            Generate new token
          </button>
          <label className={`metaGuideDevField token ${copying ? "active" : ""}`}>
            <span>Access Token</span>
            <em className="mono">
              {tokenText || "••••••••••••"}
              {copying && (
                <span className="botGuideCopyMenu">
                  {time > 6.5 ? <Check size={11} /> : <Copy size={11} />}
                  <span>{time > 6.5 ? "Copied" : "Copy"}</span>
                </span>
              )}
            </em>
          </label>
        </div>
      </div>
      <Fingertip
        x={lerp(78, 52, ramp(time, 5.2, 5.8))}
        y={lerp(88, 74, ramp(time, 5.2, 5.8))}
        visible={time > 5.1 && time < 7.1}
        pressing={copying}
      />
    </PhoneChrome>
  );
}

function PasteTarget({ platform, time }) {
  const demo = DEMO[platform];
  const fieldValue = platform === "instagram"
    ? typed(`@${demo.username}`, time, 7.3, 8.2)
    : typed(demo.displayName, time, 7.3, 8.2);
  const tokenValue = typed(demo.token, time, 8.0, 9.0);
  const done = time > 9.15;

  return (
    <div className={`botGuidePasteTarget ${done ? "done" : ""}`}>
      <span className="botGuidePasteTargetTitle">{demo.pasteTitle}</span>
      <label className={`botGuidePasteField ${fieldValue ? "filled" : ""}`}>
        <span>{demo.fieldLabel}</span>
        <em>{fieldValue || (platform === "instagram" ? "@username" : "Page nomi")}</em>
      </label>
      <label className={`botGuidePasteField ${tokenValue ? "filled" : ""}`}>
        <span>{demo.tokenLabel}</span>
        <em>{tokenValue || "EAAG… / IGQVJ…"}</em>
      </label>
      {done && (
        <span className="botGuidePasteDone">
          <Check size={13} aria-hidden="true" />
          <span>{demo.pasteDone}</span>
        </span>
      )}
    </div>
  );
}

function buildScenes(platform) {
  if (platform === "facebook") {
    return [
      {
        id: "page",
        tab: "1-video — Page topish",
        title: "Facebook Page nomini topish",
        duration: 10,
        steps: FB_SCENE_ONE_STEPS,
        Scene: FacebookSceneOne,
        Aside: null,
      },
      {
        id: "token",
        tab: "2-video — token olish",
        title: "Business Manager'dan access token",
        duration: 10,
        steps: FB_SCENE_TWO_STEPS,
        Scene: FacebookSceneTwo,
        Aside: (props) => <PasteTarget platform="facebook" {...props} />,
      },
    ];
  }

  return [
    {
      id: "username",
      tab: "1-video — username",
      title: "Instagram username qayerdan olinadi",
      duration: 10,
      steps: IG_SCENE_ONE_STEPS,
      Scene: InstagramSceneOne,
      Aside: null,
    },
    {
      id: "token",
      tab: "2-video — token",
      title: "Meta Developers'dan access token",
      duration: 10,
      steps: IG_SCENE_TWO_STEPS,
      Scene: InstagramSceneTwo,
      Aside: (props) => <PasteTarget platform="instagram" {...props} />,
    },
  ];
}

export default function MetaConnectGuideModal({ open, onClose, platform = "instagram" }) {
  const scenes = buildScenes(platform);
  const demo = DEMO[platform] || DEMO.instagram;
  const [sceneIndex, setSceneIndex] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [runId, setRunId] = useState(0);
  const scene = scenes[sceneIndex];

  const handleEnd = useCallback(() => {
    if (sceneIndex + 1 < scenes.length) setSceneIndex(sceneIndex + 1);
    else setPlaying(false);
  }, [sceneIndex, scenes.length]);

  const time = useTimeline(scene.duration, playing, `${platform}:${sceneIndex}:${runId}`, handleEnd);

  useEffect(() => {
    if (!open) return undefined;
    setSceneIndex(0);
    setRunId((current) => current + 1);
    setPlaying(!prefersReducedMotion());
    const onKeyDown = (event) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose, platform]);

  if (!open) return null;

  const activeStep = scene.steps.reduce(
    (found, step, index) => (time >= step.at ? index : found),
    0,
  );
  const progress = Math.min(100, (time / scene.duration) * 100);
  const { Scene, Aside } = scene;

  function selectScene(index) {
    setSceneIndex(index);
    setRunId((current) => current + 1);
    setPlaying(true);
  }

  function replay() {
    setRunId((current) => current + 1);
    setPlaying(true);
  }

  return (
    <div className="modalOverlay botGuideOverlay" role="presentation" onMouseDown={onClose}>
      <section
        className="modalPanel botGuideModal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="meta-connect-guide-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="modalHeader">
          <div>
            <h2 id="meta-connect-guide-title">
              <span>{demo.guideTitle}</span>
            </h2>
            <p>{demo.guideSubtitle}</p>
          </div>
          <button className="iconButton" type="button" aria-label="Yopish" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="modalContent botGuideContent">
          <div className="botGuideTabs" role="tablist">
            {scenes.map((item, index) => (
              <button
                className={`botGuideTab ${index === sceneIndex ? "active" : ""}`}
                type="button"
                role="tab"
                aria-selected={index === sceneIndex}
                key={item.id}
                onClick={() => selectScene(index)}
              >
                {item.tab}
              </button>
            ))}
          </div>

          <div className="botGuideStage">
            <div className="botGuidePhoneColumn">
              <Scene time={time} />
              <div className="botGuideControls">
                <button
                  className="botGuideControlButton"
                  type="button"
                  aria-label={playing ? "To'xtatish" : "Davom ettirish"}
                  onClick={() => setPlaying((current) => !current)}
                >
                  {playing ? <Pause size={15} /> : <Play size={15} />}
                </button>
                <button
                  className="botGuideControlButton"
                  type="button"
                  aria-label="Boshidan ko'rsatish"
                  onClick={replay}
                >
                  <RotateCcw size={15} />
                </button>
                <span className="botGuideProgressTrack">
                  <span className="botGuideProgressFill" style={{ width: `${progress}%` }} />
                </span>
                <span className="botGuideTimecode">
                  {`0:0${Math.min(9, Math.floor(time))} / 0:${scene.duration}`}
                </span>
              </div>
            </div>

            <div className="botGuideAside">
              <h3 className="botGuideAsideTitle">{scene.title}</h3>
              <ol className="botGuideSteps">
                {scene.steps.map((step, index) => (
                  <li
                    className={`botGuideStep ${index === activeStep ? "active" : ""} ${index < activeStep ? "done" : ""}`}
                    key={step.label}
                  >
                    <span className="botGuideStepMark" aria-hidden="true">
                      {index < activeStep ? <Check size={11} /> : index + 1}
                    </span>
                    <span>{step.label}</span>
                  </li>
                ))}
              </ol>
              {Aside && <Aside time={time} />}
            </div>
          </div>

          <p className="botGuideFootnote">{demo.footnote}</p>
        </div>

        <div className="deleteSourceFooter botGuideFooter">
          <button className="button primary" type="button" onClick={onClose}>
            Tushunarli, davom etaman
          </button>
        </div>
      </section>
    </div>
  );
}

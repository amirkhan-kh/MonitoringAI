import { ArrowLeft, Check, Copy, Pause, Play, RotateCcw, Search, Send, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Teaches an operator who has never touched BotFather how to create a Telegram bot
 * and where its link and token come from.
 *
 * The two "videos" are scripted DOM animations rather than mp4/gif assets: they stay
 * crisp at any zoom, weigh nothing in the bundle, and — unlike a screen recording —
 * their captions go through the same i18n MutationObserver as the rest of the UI, so
 * a Russian or English operator reads the steps in their own language. Every caption
 * below is therefore a whole sentence inside its own text node.
 */

const DEMO_BOT_NAME = "Uzum Monitoring";
const DEMO_BOT_USERNAME = "uzum_monitoring_bot";
const DEMO_BOT_LINK = `t.me/${DEMO_BOT_USERNAME}`;
const DEMO_BOT_TOKEN = "7891234567:AAH9k2Lp-QvJx0mNbR4sTuVwXyZaBcDeFgH";

/** Progressive reveal of `text` between two points on the timeline. */
function typed(text, time, from, to) {
  if (time <= from) return "";
  if (time >= to) return text;
  return text.slice(0, Math.round((text.length * (time - from)) / (to - from)));
}

/** Eased 0→1 ramp used to fly the fingertip between two screen positions. */
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

/**
 * Drives a scene clock in seconds. The elapsed time also lives in a ref so pausing and
 * resuming picks up where it stopped without making `time` an effect dependency, which
 * would restart the animation on every frame.
 *
 * `resetKey` changes whenever a fresh run starts (tab switch, auto-advance, replay). The
 * reset effect is declared before the frame loop on purpose: effects fire in declaration
 * order, so the ref is already back at zero by the time the loop recomputes its origin.
 * Resetting from the caller instead would leave the loop reading a stale elapsed time and
 * ending the new scene on its very first frame.
 */
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

function PhoneChrome({ title, subtitle, children, composer }) {
  return (
    <div className="botGuidePhone">
      <div className="botGuidePhoneNotch" aria-hidden="true" />
      <div className="botGuideStatusBar" aria-hidden="true">
        <span>9:41</span>
        <span className="botGuideStatusIcons">
          <i className="botGuideSignal" />
          <i className="botGuideWifi" />
          <i className="botGuideBattery" />
        </span>
      </div>
      <div className="botGuideAppBar">
        <ArrowLeft size={17} aria-hidden="true" />
        <span className="botGuideAppAvatar" aria-hidden="true">BF</span>
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

function Composer({ value, sending }) {
  return (
    <div className="botGuideComposer">
      <span className={`botGuideComposerField ${value ? "filled" : ""}`}>
        {value || "Message"}
        {value && <i className="botGuideCaret" />}
      </span>
      <span className={`botGuideSendButton ${sending ? "sending" : ""}`}>
        <Send size={14} aria-hidden="true" />
      </span>
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
/* Scene 1 — creating the bot inside BotFather                         */
/* ------------------------------------------------------------------ */

const SCENE_ONE_STEPS = [
  { at: 0, label: "Telegram qidiruviga @BotFather deb yozing" },
  { at: 2.6, label: "Tasdiqlangan @BotFather chatini oching" },
  { at: 3.9, label: "/newbot buyrug'ini yuboring" },
  { at: 5.8, label: "Botingizga nom bering" },
  { at: 7.6, label: "Username'ni bot so'zi bilan tugating" },
  { at: 9.2, label: "Bot yaratildi" },
];

function SceneOne({ time }) {
  const onSearchScreen = time < 2.75;

  if (onSearchScreen) {
    const query = typed("@BotFather", time, 0.5, 1.9);
    const showResult = time > 1.95;
    const tapping = time > 2.45;
    return (
      <PhoneChrome title="Telegram" subtitle="qidiruv">
          <div className="botGuideSearchBar">
            <Search size={14} aria-hidden="true" />
            <span className={query ? "filled" : ""}>{query || "Search"}</span>
            {query && <i className="botGuideCaret" />}
          </div>
          {showResult && (
            <div className={`botGuideSearchResult ${tapping ? "tapped" : ""}`}>
              <span className="botGuideAppAvatar" aria-hidden="true">BF</span>
              <span className="botGuideSearchResultBody">
                <strong>
                  BotFather
                  <i className="botGuideVerified" aria-hidden="true"><Check size={9} /></i>
                </strong>
                <em>@BotFather</em>
              </span>
            </div>
          )}
          <Fingertip
            x={lerp(78, 32, ramp(time, 2.1, 2.45))}
            y={lerp(86, 30, ramp(time, 2.1, 2.45))}
            visible={time > 2.05}
            pressing={tapping}
          />
      </PhoneChrome>
    );
  }

  const localTime = time;
  const composerText = localTime < 4.55
    ? typed("/newbot", localTime, 3.95, 4.5)
    : localTime < 7.25
      ? typed(DEMO_BOT_NAME, localTime, 6.1, 7.2)
      : typed(DEMO_BOT_USERNAME, localTime, 7.95, 9.0);
  const sending = [4.55, 7.25, 9.05].some((mark) => localTime >= mark && localTime < mark + 0.25);

  return (
    <PhoneChrome
      title="BotFather"
      subtitle="bot"
      composer={<Composer value={composerText} sending={sending} />}
    >
      <div className="botGuideChat">
        {localTime > 4.6 && <p className="botGuideBubble out">/newbot</p>}
        {localTime > 4.9 && localTime < 5.4 && <p className="botGuideBubble in typing"><i /><i /><i /></p>}
        {localTime > 5.4 && (
          <p className="botGuideBubble in">
            Alright, a new bot. How are we going to call it? Please choose a name for your bot.
          </p>
        )}
        {localTime > 7.3 && <p className="botGuideBubble out">{DEMO_BOT_NAME}</p>}
        {localTime > 7.6 && (
          <p className="botGuideBubble in">
            Good. Now let's choose a username for your bot. It must end in `bot`.
          </p>
        )}
        {localTime > 9.1 && <p className="botGuideBubble out">{DEMO_BOT_USERNAME}</p>}
        {localTime > 9.35 && (
          <p className="botGuideBubble in success">
            Done! Congratulations on your new bot.
          </p>
        )}
      </div>
    </PhoneChrome>
  );
}

/* ------------------------------------------------------------------ */
/* Scene 2 — copying the link and the token into MonitoringAI          */
/* ------------------------------------------------------------------ */

const SCENE_TWO_STEPS = [
  { at: 0, label: "BotFather yuborgan xabarda link ham, token ham bor" },
  { at: 1.5, label: "t.me linkini bosib turing va Copy'ni tanlang" },
  { at: 3.4, label: "Linkni «Bot link yoki username» maydoniga qo'ying" },
  { at: 5.2, label: "Endi HTTP API tokenini xuddi shunday nusxalang" },
  { at: 7.3, label: "Tokenni «Bot token» maydoniga qo'ying" },
  { at: 9.1, label: "Ikkala maydon to'ldi — endi saqlash mumkin" },
];

function SceneTwo({ time }) {
  const copyingLink = time >= 1.7 && time < 3.2;
  const copyingToken = time >= 5.4 && time < 7.1;
  const linkCopied = time >= 2.8;
  const tokenCopied = time >= 6.7;

  const fingerTarget = time < 4.9
    ? { x: lerp(80, 44, ramp(time, 1.2, 1.75)), y: lerp(88, 47, ramp(time, 1.2, 1.75)) }
    : { x: lerp(44, 50, ramp(time, 4.9, 5.5)), y: lerp(47, 66, ramp(time, 4.9, 5.5)) };

  return (
    <PhoneChrome title="BotFather" subtitle="bot">
      <div className="botGuideChat">
        <p className="botGuideBubble in botGuideCredentials">
          <span className="botGuideCredLine">Done! Congratulations on your new bot.</span>
          <span className="botGuideCredLine">You will find it at</span>
          <mark className={`botGuideCopyable ${copyingLink ? "active" : ""} ${linkCopied ? "copied" : ""}`}>
            {DEMO_BOT_LINK}
            {copyingLink && (
              <span className="botGuideCopyMenu">
                {linkCopied ? <Check size={11} aria-hidden="true" /> : <Copy size={11} aria-hidden="true" />}
                <span>{linkCopied ? "Copied" : "Copy"}</span>
              </span>
            )}
          </mark>
          <span className="botGuideCredLine">Use this token to access the HTTP API:</span>
          <mark className={`botGuideCopyable token ${copyingToken ? "active" : ""} ${tokenCopied ? "copied" : ""}`}>
            {DEMO_BOT_TOKEN}
            {copyingToken && (
              <span className="botGuideCopyMenu">
                {tokenCopied ? <Check size={11} aria-hidden="true" /> : <Copy size={11} aria-hidden="true" />}
                <span>{tokenCopied ? "Copied" : "Copy"}</span>
              </span>
            )}
          </mark>
          <span className="botGuideCredLine warn">Keep your token secure and store it safely.</span>
        </p>
      </div>
      <Fingertip
        x={fingerTarget.x}
        y={fingerTarget.y}
        visible={time > 1.15 && time < 7.2}
        pressing={copyingLink || copyingToken}
      />
    </PhoneChrome>
  );
}

/** The destination fields, so the operator sees exactly where each value lands. */
function PasteTarget({ time }) {
  const linkValue = typed(`https://${DEMO_BOT_LINK}`, time, 3.5, 4.6);
  const tokenValue = typed(DEMO_BOT_TOKEN, time, 7.4, 8.7);
  const done = time > 9.0;

  return (
    <div className={`botGuidePasteTarget ${done ? "done" : ""}`}>
      <span className="botGuidePasteTargetTitle">MonitoringAI — Telegram bot</span>
      <label className={`botGuidePasteField ${linkValue ? "filled" : ""}`}>
        <span>Bot link yoki username</span>
        <em>{linkValue || "https://t.me/…"}</em>
      </label>
      <label className={`botGuidePasteField ${tokenValue ? "filled" : ""}`}>
        <span>Bot token</span>
        <em>{tokenValue || "123456:ABC…"}</em>
      </label>
      {done && (
        <span className="botGuidePasteDone">
          <Check size={13} aria-hidden="true" />
          <span>Bot ulanishga tayyor</span>
        </span>
      )}
    </div>
  );
}

const SCENES = [
  {
    id: "create",
    tab: "1-video — botni yaratish",
    title: "BotFather orqali yangi bot yaratish",
    duration: 10,
    steps: SCENE_ONE_STEPS,
    Scene: SceneOne,
    Aside: null,
  },
  {
    id: "credentials",
    tab: "2-video — link va token",
    title: "Bot linki va tokenini olish",
    duration: 10,
    steps: SCENE_TWO_STEPS,
    Scene: SceneTwo,
    Aside: PasteTarget,
  },
];

export default function BotFatherGuideModal({ open, onClose }) {
  const [sceneIndex, setSceneIndex] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [runId, setRunId] = useState(0);
  const scene = SCENES[sceneIndex];

  // The first scene hands over to the second; the second stops on its final frame.
  const handleEnd = useCallback(() => {
    if (sceneIndex + 1 < SCENES.length) setSceneIndex(sceneIndex + 1);
    else setPlaying(false);
  }, [sceneIndex]);

  const time = useTimeline(scene.duration, playing, `${sceneIndex}:${runId}`, handleEnd);

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
  }, [open, onClose]);

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
        aria-labelledby="botfather-guide-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="modalHeader">
          <div>
            <h2 id="botfather-guide-title">
              <span>Telegram bot yaratish qo'llanmasi</span>
            </h2>
            <p>Ikki qisqa ko'rsatmani ko'ring: bot qanday yaratiladi va link bilan token qayerdan olinadi.</p>
          </div>
          <button className="iconButton" type="button" aria-label="Yopish" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="modalContent botGuideContent">
          <div className="botGuideTabs" role="tablist">
            {SCENES.map((item, index) => (
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

          <p className="botGuideFootnote">
            Token parol bilan teng: uni hech kimga bermang. Noto'g'ri joyga yuborilgan bo'lsa, BotFather'dagi
            /revoke buyrug'i orqali yangisini oling.
          </p>
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

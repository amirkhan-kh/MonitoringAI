import {
  AlertTriangle,
  Brain,
  CheckCircle2,
  Clock3,
  Layers3,
  Radio,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import { translateUiText, useUiLanguage } from "../i18n";
import { PercentGauge, PipelineGauge } from "./TrendChart";

const platformCopy = {
  telegram: {
    name: "Telegram",
    sourceLabel: "Source",
    mentionLabel: "Mention",
    flow: ["Source", "Live/backfill", "AI", "Risk"],
    production: "Kanal va discussion avtomatik yig'iladi.",
    tone: "telegram",
  },
  youtube: {
    name: "YouTube",
    sourceLabel: "Source",
    mentionLabel: "Video/comment",
    flow: ["Kanal", "Sync", "AI", "Risk"],
    production: "Video va commentlar API orqali yangilanadi.",
    tone: "youtube",
  },
  instagram: {
    name: "Instagram",
    sourceLabel: "Akkaunt",
    mentionLabel: "Comment",
    flow: ["Akkaunt", "Token", "AI", "Webhook"],
    production: "Token va Meta ruxsatiga bog'liq.",
    tone: "instagram",
  },
  facebook: {
    name: "Facebook",
    sourceLabel: "Page",
    mentionLabel: "Comment",
    flow: ["Page", "Poller", "AI", "Javob"],
    production: "Page commentlari token bilan olinadi.",
    tone: "facebook",
  },
};

function compactNumber(value) {
  return new Intl.NumberFormat("uz-UZ", { notation: "compact", maximumFractionDigits: 1 }).format(value || 0);
}

function percent(value) {
  return `${Math.round((value || 0) * 100)}%`;
}

function sourceTotal(sources, summary) {
  if (typeof summary?.sources_total === "number") return summary.sources_total;
  return sources.length;
}

function activeSources(sources, summary) {
  if (!sources?.length && typeof summary?.sources_total === "number") return summary.sources_total;
  return sources.filter((source) => source.active !== false).length;
}

function invalidSources(sources) {
  return sources.filter((source) => source.active !== false && source.token_status === "invalid").length;
}

function mentionTotal(summary) {
  return summary?.mentions_total || 0;
}

function latestMentionCount(summary) {
  return Array.isArray(summary?.latest_mentions) ? summary.latest_mentions.length : 0;
}

function analyzedTotal(summary) {
  if (typeof summary?.analyzed_total === "number") return summary.analyzed_total;
  return highRiskTotal(summary);
}

function aiStats(summary) {
  const highRisk = highRiskTotal(summary);
  const analyzed = Math.max(analyzedTotal(summary), highRisk);
  const mentions = Math.max(mentionTotal(summary), latestMentionCount(summary), analyzed);
  const explicitCoverage = typeof summary?.analysis_coverage === "number" ? summary.analysis_coverage : null;
  const coverage = explicitCoverage !== null && explicitCoverage > 0
    ? explicitCoverage
    : mentions
      ? analyzed / mentions
      : 0;

  return {
    analyzed,
    coverage: Math.max(0, Math.min(1, coverage)),
    highRisk,
    mentions,
  };
}

function highRiskTotal(summary) {
  if (typeof summary?.high_risk === "number") return summary.high_risk;
  const risk = summary?.risk_counts || {};
  return (risk.high || 0) + (risk.critical || 0);
}

function secondaryMentionTotal(platform, summary) {
  if (platform === "youtube") return summary?.comments_total || 0;
  if (platform === "instagram") return summary?.comments_total || summary?.mentions_direct_total || 0;
  if (platform === "facebook") return summary?.comments_total || 0;
  return highRiskTotal(summary);
}

function healthTone({ sources, summary, status }) {
  if (status && status.configured === false) return "warning";
  if (invalidSources(sources) > 0) return "danger";
  if (sourceTotal(sources, summary) === 0) return "warning";
  return "good";
}

function sourceStatusText({ platform, sources, summary, status, lng }) {
  const copy = platformCopy[platform] || platformCopy.telegram;
  if (status && status.configured === false) {
    return translateUiText(`${copy.name} API sozlanmagan`, { lng });
  }
  const invalid = invalidSources(sources);
  if (invalid) return translateUiText(`${invalid} ta token yaroqsiz`, { lng });
  const total = sourceTotal(sources, summary);
  const active = activeSources(sources, summary);
  if (!total) return translateUiText(`${copy.sourceLabel} qo'shilmagan`, { lng });
  return translateUiText(`${active}/${total} faol`, { lng });
}

function statusIcon(tone) {
  if (tone === "danger") return AlertTriangle;
  if (tone === "warning") return Clock3;
  return CheckCircle2;
}

/** How many pipeline stages are “ready” based on live data. */
function pipelineActiveCount({ platform, sources, summary, status, ai }) {
  const copy = platformCopy[platform] || platformCopy.telegram;
  const totalSources = sourceTotal(sources, summary);
  const hasSources = totalSources > 0 && !(status && status.configured === false);
  const hasMentions = mentionTotal(summary) > 0;
  const hasAi = (ai.analyzed || 0) > 0 || ai.coverage > 0;
  const stages = [
    hasSources,
    hasMentions || hasSources,
    hasAi,
    hasAi,
  ];
  if (!hasSources) stages[1] = false;
  return {
    steps: copy.flow,
    active: stages.filter(Boolean).length,
  };
}

export function MonitoringInsights({ platform, summary, sources = [], status = null, loading = false }) {
  const lng = useUiLanguage();
  const copy = platformCopy[platform] || platformCopy.telegram;
  const tone = healthTone({ sources, summary, status });
  const StatusIcon = statusIcon(tone);
  const ai = aiStats(summary);
  const coverage = ai.coverage;
  const totalMentions = mentionTotal(summary);
  const secondary = secondaryMentionTotal(platform, summary);
  const active = activeSources(sources, summary);
  const totalSources = sourceTotal(sources, summary);
  const productionRatio = totalSources ? active / totalSources : 0;
  const pipeline = pipelineActiveCount({ platform, sources, summary, status, ai });
  const signalShare = totalMentions ? Math.min(1, secondary / totalMentions) : 0;
  const tt = (value) => translateUiText(value, { lng });
  const mentionFlowLabel = tt(`${copy.mentionLabel} oqimi`);
  const sourceActiveLabel = tt(`${copy.sourceLabel} faol`);
  const pipelineLabel = tt(`Signal oqimi · ${pipeline.active}/${pipeline.steps.length}`);
  const translatedSteps = pipeline.steps.map((step) => tt(step));

  if (loading) {
    return (
      <section className="insightsGrid isLoading" aria-busy="true">
        {Array.from({ length: 4 }).map((_, index) => (
          <article className="insightPanel skeletonInsight" key={`insight-skeleton-${index}`}>
            <span className="skeletonIcon" />
            <span className="skeletonText heading" />
            <span className="skeletonText wide" />
            <span className="skeletonText mid" />
          </article>
        ))}
      </section>
    );
  }

  return (
    <section className="insightsGrid insightsGrid--mixed">
      {/* Production — status + big numbers (no gauge; ratio is not the main story) */}
      <article className={`insightPanel insightPanel--stat ${tone}`}>
        <div className="insightHead">
          <span className="insightIcon"><StatusIcon size={18} /></span>
          <div>
            <strong data-i18n-ignore="true">{tt("Production")}</strong>
            <p data-i18n-ignore="true">{sourceStatusText({ platform, sources, summary, status, lng })}</p>
          </div>
        </div>
        <div className="insightHeroMetric">
          <strong className="insightHeroValue">
            {active}<span className="insightHeroSep">/</span>{totalSources}
          </strong>
          <span className="insightHeroLabel" data-i18n-ignore="true">{sourceActiveLabel}</span>
        </div>
        <div className="insightMeterTrack" aria-hidden="true">
          <i
            className={`tone-${tone === "good" ? "positive" : tone === "danger" ? "negative" : "warning"}`}
            style={{ width: `${Math.max(totalSources ? 6 : 0, productionRatio * 100)}%` }}
          />
        </div>
        <small data-i18n-ignore="true">{tt(copy.production)}</small>
      </article>

      {/* Mention — volume focus with dual metrics + soft fill */}
      <article className="insightPanel insightPanel--stat">
        <div className="insightHead">
          <span className="insightIcon"><Layers3 size={18} /></span>
          <div>
            <strong data-i18n-ignore="true">{tt("Mention")}</strong>
            <p data-i18n-ignore="true">{mentionFlowLabel}</p>
          </div>
        </div>
        <div className="insightHeroMetric">
          <strong className="insightHeroValue">{compactNumber(totalMentions)}</strong>
          <span className="insightHeroLabel" data-i18n-ignore="true">{tt("Jami mention")}</span>
        </div>
        <div className="insightDualStats">
          <div>
            <span data-i18n-ignore="true">{tt("Signal")}</span>
            <b>{compactNumber(secondary)}</b>
          </div>
          <div>
            <span data-i18n-ignore="true">{tt("Ulush")}</span>
            <b>{percent(signalShare)}</b>
          </div>
        </div>
        <div className="insightMeterTrack" aria-hidden="true">
          <i
            className={`tone-${copy.tone || "accent"}`}
            style={{ width: `${Math.max(totalMentions ? 8 : 0, Math.min(100, signalShare * 100 || (totalMentions ? 100 : 0)))}%` }}
          />
        </div>
      </article>

      {/* AI qamrov — keep ECharts gauge */}
      <article className="insightPanel insightPanel--gauge">
        <div className="insightHead">
          <span className="insightIcon"><Brain size={18} /></span>
          <div>
            <strong data-i18n-ignore="true">{tt("AI qamrov")}</strong>
            <p data-i18n-ignore="true">{tt("Tahlil ulushi")}</p>
          </div>
        </div>
        <PercentGauge
          value={coverage}
          max={100}
          height={108}
          tone="positive"
          compact
          showTicks
          showLabels
        />
        <div className="insightSplit">
          <span data-i18n-ignore="true">{tt("Qamrov")} <b>{percent(coverage)}</b></span>
          <span data-i18n-ignore="true">{tt("Risk")} <b>{compactNumber(ai.highRisk)}</b></span>
        </div>
        <div className="insightSplit compact">
          <span data-i18n-ignore="true">{tt("Tahlil")} <b>{compactNumber(ai.analyzed)}/{compactNumber(ai.mentions)}</b></span>
        </div>
      </article>

      {/* Zanjir — keep pipeline gauge */}
      <article className="insightPanel insightPanel--gauge workflowPanel">
        <div className="insightHead">
          <span className="insightIcon"><Workflow size={18} /></span>
          <div>
            <strong data-i18n-ignore="true">{tt("Zanjir")}</strong>
            <p data-i18n-ignore="true">{pipelineLabel}</p>
          </div>
        </div>
        <PipelineGauge
          steps={translatedSteps}
          activeCount={pipeline.active}
          height={96}
          tone="accent"
        />
        <div className="workflowSteps workflowSteps--compact">
          {translatedSteps.map((item, index) => {
            const ready = index < pipeline.active;
            return (
              <span key={`${pipeline.steps[index]}-${item}`} className={ready ? "isReady" : ""} data-i18n-ignore="true">
                {index === 0 ? <Radio size={13} /> : index === 2 ? <Brain size={13} /> : <ShieldCheck size={13} />}
                {item}
              </span>
            );
          })}
        </div>
      </article>
    </section>
  );
}

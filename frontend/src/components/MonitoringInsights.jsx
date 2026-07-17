import {
  AlertTriangle,
  Brain,
  CheckCircle2,
  Clock3,
  Gauge,
  Layers3,
  Radio,
  ShieldCheck,
  Workflow,
} from "lucide-react";

const platformCopy = {
  telegram: {
    name: "Telegram",
    sourceLabel: "Source",
    mentionLabel: "Mention",
    flow: ["Source qo'shish", "Backfill yoki live bot", "AI tahlil", "Risk javobi"],
    production: "Kanal, group va discussion commentlari source holatiga qarab avtomatik yig'iladi.",
  },
  youtube: {
    name: "YouTube",
    sourceLabel: "Source",
    mentionLabel: "Video/comment",
    flow: ["Kanal yoki hashtag", "Sync", "AI tahlil", "Trend va risk"],
    production: "Kanal uploads, video commentlari va hashtag manbalari API key orqali yangilanadi.",
  },
  instagram: {
    name: "Instagram",
    sourceLabel: "Akkaunt",
    mentionLabel: "Comment/@mention",
    flow: ["Business akkaunt", "Token/poller", "AI tahlil", "Meta webhook"],
    production: "Own account ishlashi token va Meta permission holatiga bog'liq. Keng ommaviy oqim uchun App Review kerak bo'lishi mumkin.",
  },
  facebook: {
    name: "Facebook",
    sourceLabel: "Page",
    mentionLabel: "Comment/reply",
    flow: ["Page token", "Poller/webhook", "AI tahlil", "Inboxga javob"],
    production: "Page commentlari token va permission bilan olinadi. Business portfolio cheklovi bo'lsa avval Meta tomoni hal qilinadi.",
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

function sourceStatusText({ platform, sources, summary, status }) {
  const copy = platformCopy[platform] || platformCopy.telegram;
  if (status && status.configured === false) return `${copy.name} API sozlanmagan`;
  const invalid = invalidSources(sources);
  if (invalid) return `${invalid} ta token yaroqsiz`;
  const total = sourceTotal(sources, summary);
  const active = activeSources(sources, summary);
  if (!total) return `${copy.sourceLabel} qo'shilmagan`;
  return `${active}/${total} faol`;
}

function statusIcon(tone) {
  if (tone === "danger") return AlertTriangle;
  if (tone === "warning") return Clock3;
  return CheckCircle2;
}

export function MonitoringInsights({ platform, summary, sources = [], status = null, loading = false }) {
  const copy = platformCopy[platform] || platformCopy.telegram;
  const tone = healthTone({ sources, summary, status });
  const StatusIcon = statusIcon(tone);
  const ai = aiStats(summary);
  const coverage = ai.coverage;
  const totalMentions = mentionTotal(summary);
  const secondary = secondaryMentionTotal(platform, summary);
  const active = activeSources(sources, summary);
  const totalSources = sourceTotal(sources, summary);

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
    <section className="insightsGrid">
      <article className={`insightPanel ${tone}`}>
        <div className="insightHead">
          <span className="insightIcon"><StatusIcon size={18} /></span>
          <div>
            <strong>Production holati</strong>
            <p>{sourceStatusText({ platform, sources, summary, status })}</p>
          </div>
        </div>
        <div className="insightMetricLine">
          <span>{copy.sourceLabel}</span>
          <b>{active}/{totalSources}</b>
        </div>
        <small>{copy.production}</small>
      </article>

      <article className="insightPanel">
        <div className="insightHead">
          <span className="insightIcon"><Layers3 size={18} /></span>
          <div>
            <strong>Mention oqimi</strong>
            <p>{copy.mentionLabel} bir joyda ko'rinadi.</p>
          </div>
        </div>
        <div className="qualityMeter">
          <i style={{ width: `${Math.max(3, Math.min(100, totalMentions ? 100 : 3))}%` }} />
        </div>
        <div className="insightSplit">
          <span>Jami <b>{compactNumber(totalMentions)}</b></span>
          <span>Qo'shimcha signal <b>{compactNumber(secondary)}</b></span>
        </div>
      </article>

      <article className="insightPanel">
        <div className="insightHead">
          <span className="insightIcon"><Brain size={18} /></span>
          <div>
            <strong>AI aniqlik nazorati</strong>
            <p>Tahlil qilingan mentionlar ulushi.</p>
          </div>
        </div>
        <div className="qualityMeter ai">
          <i style={{ width: `${Math.max(3, coverage * 100)}%` }} />
        </div>
        <div className="insightSplit">
          <span>Qamrov <b>{percent(coverage)}</b></span>
          <span>High risk <b>{compactNumber(ai.highRisk)}</b></span>
        </div>
        <div className="insightSplit compact">
          <span>Tahlil <b>{compactNumber(ai.analyzed)}/{compactNumber(ai.mentions)}</b></span>
        </div>
      </article>

      <article className="insightPanel workflowPanel">
        <div className="insightHead">
          <span className="insightIcon"><Workflow size={18} /></span>
          <div>
            <strong>Ishlash zanjiri</strong>
            <p>Brand signali yo'qolmasligi uchun ketma-ketlik.</p>
          </div>
        </div>
        <div className="workflowSteps">
          {copy.flow.map((item, index) => (
            <span key={item}>
              {index === 0 ? <Radio size={14} /> : index === 2 ? <Gauge size={14} /> : <ShieldCheck size={14} />}
              {item}
            </span>
          ))}
        </div>
      </article>
    </section>
  );
}

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  BarChart3,
  Brain,
  ExternalLink,
  Eye,
  Facebook,
  Heart,
  Instagram,
  MessageSquareText,
  PlusCircle,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { endpoints, readSelectedBrandId, resolveSelectedBrandId } from "../api/client";
import { PageHeader } from "../components/PageHeader";
import { Sidebar } from "../components/Sidebar";
import { StatsBar } from "../components/StatsBar";
import { TelegramIcon, YouTubeIcon } from "../components/BrandIcons";

const periodOptions = [
  { key: "day", label: "Kun", value: 1, interval: "hour" },
  { key: "week", label: "Hafta", value: 7, interval: "day" },
  { key: "month", label: "Oy", value: 30, interval: "day" },
  { key: "quarter", label: "90 kun", value: 90, interval: "week" },
];

const intervalLabels = {
  hour: "Soatlik",
  day: "Kunlik",
  week: "Haftalik",
  month: "Oylik",
};

const chartSeries = [
  { key: "total", label: "Jami", tone: "total" },
  { key: "telegram", label: "Telegram", tone: "telegram" },
  { key: "youtube", label: "YouTube", tone: "youtube" },
  { key: "instagram", label: "Instagram", tone: "instagram" },
  { key: "facebook", label: "Facebook", tone: "facebook" },
];

const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Tashkent";

const sentimentLabels = {
  positive: "Ijobiy",
  neutral: "Neytral",
  negative: "Salbiy",
  mixed: "Aralash",
  unknown: "Noma'lum",
};

const riskLabels = {
  low: "Past",
  medium: "O'rta",
  high: "Yuqori",
  critical: "Kritik",
  unknown: "Noma'lum",
};

function maxValue(items, key = "value") {
  return Math.max(1, ...items.map((item) => item[key] || 0));
}

function compactNumber(value) {
  return new Intl.NumberFormat("uz-UZ", { notation: "compact", maximumFractionDigits: 1 }).format(value || 0);
}

function percent(value) {
  return `${Math.round((value || 0) * 100)}%`;
}

function score(value) {
  return Number(value || 0).toFixed(2);
}

function changeLabel(value) {
  if (value > 0) return `+${value}%`;
  return `${value}%`;
}

function platformCoverageDetail(ai) {
  const platformLabels = {
    telegram: "Telegram",
    youtube: "YouTube",
    instagram: "Instagram",
    facebook: "Facebook",
  };
  const platforms = ai?.platforms || {};
  const rows = Object.entries(platforms)
    .filter(([, metric]) => (metric?.mentions || 0) > 0)
    .map(([platform, metric]) => `${platformLabels[platform] || platform}: ${percent(metric.coverage || 0)}`);
  return rows.length ? rows.join(" · ") : "AI tahlil uchun mention yo'q";
}

function reliabilityDetail(ai) {
  const failed = ai?.failed_mentions || 0;
  const processed = ai?.processed_mentions || 0;
  const balance = percent(ai?.platform_balance || 0);
  return processed ? `Processed ${processed} · Xato ${failed} · Balans ${balance}` : "Hali AI tahlil yo'q";
}

function trendIcon(direction) {
  if (direction === "pasayish") return TrendingDown;
  return TrendingUp;
}

function buildChartModel(rows, seriesList = chartSeries) {
  const width = 760;
  const height = 250;
  const pad = { top: 18, right: 18, bottom: 46, left: 58 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const max = Math.max(1, ...rows.flatMap((row) => seriesList.map((series) => row[series.key] || 0)));
  const step = rows.length > 1 ? plotWidth / (rows.length - 1) : plotWidth;
  const pointList = (key) =>
    rows.map((row, index) => {
      const x = pad.left + index * step;
      const y = pad.top + plotHeight - ((row[key] || 0) / max) * plotHeight;
      return { x, y, value: row[key] || 0, label: row.label || row.bucket };
    });
  const points = (key) => pointList(key).map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
  const tickRatios = [0, 0.25, 0.5, 0.75, 1];
  const yTicks = tickRatios.map((ratio) => {
    const value = Math.round(max * ratio);
    return {
      value,
      y: pad.top + plotHeight - ratio * plotHeight,
    };
  });
  const labelEvery = Math.max(1, Math.ceil(rows.length / 6));
  const xLabels = rows
    .map((row, index) => ({ index, label: row.label || row.bucket }))
    .filter((item) => item.index === 0 || item.index === rows.length - 1 || item.index % labelEvery === 0)
    .map((item) => ({
      ...item,
      x: pad.left + item.index * step,
    }));
  return { width, height, pad, plotWidth, plotHeight, points, pointList, yTicks, xLabels };
}

function DashboardLineChart({ rows, period }) {
  const safeRows = rows || [];
  const model = buildChartModel(safeRows);
  const totals = chartSeries.reduce((acc, series) => {
    acc[series.key] = safeRows.reduce((sum, row) => sum + (row[series.key] || 0), 0);
    return acc;
  }, {});
  const peak = safeRows.reduce(
    (best, row) => ((row.total || 0) > (best.total || 0) ? row : best),
    safeRows[0] || { total: 0, label: "-" },
  );

  return (
    <div className="analyticsChart" aria-label="Mention trend chart">
      <svg viewBox={`0 0 ${model.width} ${model.height}`} preserveAspectRatio="none">
        {model.yTicks.map((tick) => (
          <g className="chartGrid" key={tick.y}>
            <line x1={model.pad.left} x2={model.width - model.pad.right} y1={tick.y} y2={tick.y} />
            <text x={model.pad.left - 12} y={tick.y + 4}>{compactNumber(tick.value)}</text>
          </g>
        ))}
        <line
          className="chartAxis"
          x1={model.pad.left}
          x2={model.pad.left}
          y1={model.pad.top}
          y2={model.pad.top + model.plotHeight}
        />
        <line
          className="chartAxis"
          x1={model.pad.left}
          x2={model.width - model.pad.right}
          y1={model.pad.top + model.plotHeight}
          y2={model.pad.top + model.plotHeight}
        />
        {chartSeries.map((series) => (
          <polyline key={series.key} className={`chartLine ${series.tone}`} points={model.points(series.key)} />
        ))}
        {chartSeries.map((series) => (
          <g className={`chartDots ${series.tone}`} key={`${series.key}-dots`}>
            {model.pointList(series.key).map((point, index) => (
              <circle key={`${series.key}-${index}`} cx={point.x} cy={point.y} r="4">
                <title>{`${series.label}: ${compactNumber(point.value)} (${point.label})`}</title>
              </circle>
            ))}
          </g>
        ))}
        {model.xLabels.map((item) => (
          <text className="chartXLabel" key={`${item.index}-${item.label}`} x={item.x} y={model.height - 14}>
            {item.label}
          </text>
        ))}
        <text className="chartYLabel" x="14" y="20">Mention</text>
      </svg>
      <div className="chartLegend">
        {chartSeries.map((series) => (
          <span key={series.key}><i className={series.tone} /> {series.label}</span>
        ))}
        <span className="chartTimezone">
          {intervalLabels[period?.interval] || "Kunlik"} · {period?.timezone || "Asia/Tashkent"} {period?.utc_offset || "+05:00"}
        </span>
      </div>
      <div className="chartSummary">
        <span className="total">Jami <strong>{compactNumber(totals.total)}</strong></span>
        <span className="telegram">Telegram <strong>{compactNumber(totals.telegram)}</strong></span>
        <span className="youtube">YouTube <strong>{compactNumber(totals.youtube)}</strong></span>
        <span className="instagram">Instagram <strong>{compactNumber(totals.instagram)}</strong></span>
        <span className="facebook">Facebook <strong>{compactNumber(totals.facebook)}</strong></span>
        <span>Pik davr <strong>{peak.label || "-"}</strong> · {compactNumber(peak.total)}</span>
      </div>
    </div>
  );
}

function SinglePlatformChart({ rows, series, period }) {
  const safeRows = rows || [];
  const model = buildChartModel(safeRows, [series]);
  const total = safeRows.reduce((sum, row) => sum + (row[series.key] || 0), 0);
  const peak = safeRows.reduce(
    (best, row) => ((row[series.key] || 0) > (best[series.key] || 0) ? row : best),
    safeRows[0] || { [series.key]: 0, label: "-" },
  );

  return (
    <div className="platformChart" aria-label={`${series.label} trend chart`}>
      <svg viewBox={`0 0 ${model.width} ${model.height}`} preserveAspectRatio="none">
        {model.yTicks.map((tick) => (
          <g className="chartGrid" key={tick.y}>
            <line x1={model.pad.left} x2={model.width - model.pad.right} y1={tick.y} y2={tick.y} />
            <text x={model.pad.left - 12} y={tick.y + 4}>{compactNumber(tick.value)}</text>
          </g>
        ))}
        <line className="chartAxis" x1={model.pad.left} x2={model.pad.left} y1={model.pad.top} y2={model.pad.top + model.plotHeight} />
        <line className="chartAxis" x1={model.pad.left} x2={model.width - model.pad.right} y1={model.pad.top + model.plotHeight} y2={model.pad.top + model.plotHeight} />
        <polyline className={`chartLine ${series.tone}`} points={model.points(series.key)} />
        <g className={`chartDots ${series.tone}`}>
          {model.pointList(series.key).map((point, index) => (
            <circle key={`${series.key}-${index}`} cx={point.x} cy={point.y} r="4">
              <title>{`${series.label}: ${compactNumber(point.value)} (${point.label})`}</title>
            </circle>
          ))}
        </g>
        {model.xLabels.map((item) => (
          <text className="chartXLabel" key={`${series.key}-${item.index}-${item.label}`} x={item.x} y={model.height - 14}>
            {item.label}
          </text>
        ))}
      </svg>
      <div className="platformChartMeta">
        <span><i className={series.tone} /> {intervalLabels[period?.interval] || "Kunlik"}</span>
        <strong>{compactNumber(total)}</strong>
        <span>Pik: {peak.label || "-"} · {compactNumber(peak[series.key] || 0)}</span>
      </div>
    </div>
  );
}

function ProgressRows({ rows }) {
  const max = maxValue(rows);
  return (
    <div className="barList compact">
      {rows.map((item) => (
        <div className={`barRow ${item.tone || ""}`} key={item.label}>
          <span>{item.icon ? <item.icon size={16} /> : null} {item.label}</span>
          <div className="barTrack">
            <i className={item.tone || ""} style={{ width: `${Math.max(4, (item.value / max) * 100)}%` }} />
          </div>
          <strong>{compactNumber(item.value)}</strong>
        </div>
      ))}
    </div>
  );
}

function Distribution({ rows, type }) {
  const total = rows.reduce((sum, item) => sum + item.value, 0);
  if (!total) return <div className="empty">Hali AI tahlil natijasi yo'q</div>;

  return (
    <div className="distribution">
      <div className="distributionBar">
        {rows.map((item) => (
          <i
            key={item.key}
            className={`${type}-${item.key}`}
            style={{ width: `${Math.max(4, (item.value / total) * 100)}%` }}
            title={`${item.label}: ${item.value}`}
          />
        ))}
      </div>
      <div className="distributionList">
        {rows.map((item) => (
          <span key={item.key}>
            <i className={`${type}-${item.key}`} />
            {item.label} <strong>{item.value}</strong>
          </span>
        ))}
      </div>
    </div>
  );
}

function OfficialSourceSetup({ sources, filter }) {
  const platforms = [
    {
      label: "Telegram",
      tone: "telegram",
      icon: TelegramIcon,
      official: sources.official_telegram || 0,
      total: sources.telegram || 0,
      description: "Rasmiy kanal/guruh",
      status: "Faol",
    },
    {
      label: "YouTube",
      tone: "youtube",
      icon: YouTubeIcon,
      official: sources.official_youtube || 0,
      total: sources.youtube || 0,
      description: "Rasmiy kanal/video",
      status: "Faol",
    },
    {
      label: "Instagram",
      tone: "instagram",
      icon: Instagram,
      official: sources.official_instagram || 0,
      total: sources.instagram || 0,
      description: "Business akkaunt",
      status: sources.instagram ? "Ulangan" : "Kutilmoqda",
    },
    {
      label: "Facebook",
      tone: "facebook",
      icon: Facebook,
      official: sources.official_facebook || 0,
      total: sources.facebook || 0,
      description: "Facebook Page",
      status: sources.facebook ? "Ulangan" : "Kutilmoqda",
    },
  ];

  return (
    <article className="dashboardPanel panel sourceSetupPanel compactSetupPanel">
      <div className="sectionHeader compact">
        <div>
          <h2>Official source profili</h2>
          <p>{filter.brand_name || "Brand"} rasmiy kanal/bloglari profil sahifasida boshqariladi.</p>
        </div>
        <a className="button secondary linkButton" href="/profile">
          <ExternalLink size={16} />
          <span>Profilga o'tish</span>
        </a>
      </div>
      <div className="sourceSetupGrid">
        {platforms.map((item) => {
          const Icon = item.icon;
          return (
            <div className={`sourceSetupCard ${item.tone}`} key={item.label}>
              <span className="setupIcon"><Icon size={18} /></span>
              <span>
                <strong>{item.label}</strong>
                <em>{item.description}</em>
              </span>
              <b>{item.official}/{item.total}</b>
              <small>{item.status}</small>
            </div>
          );
        })}
      </div>
    </article>
  );
}

const platformCardConfig = {
  telegram: {
    key: "telegram",
    label: "Telegram",
    tone: "telegram",
    Icon: TelegramIcon,
    href: "/telegram-monitoring",
    description: "Kanal, group va discussion commentlari oqimi.",
    metrics: (mentions, engagement, sources) => [
      { label: "Post", value: mentions.telegram_posts || 0 },
      { label: "Comment/chat", value: mentions.telegram_comments || 0 },
      { label: "Reaction", value: engagement.telegram_reactions || 0 },
      { label: "Official source", value: sources.official_telegram || 0 },
    ],
  },
  youtube: {
    key: "youtube",
    label: "YouTube",
    tone: "youtube",
    Icon: YouTubeIcon,
    href: "/youtube-monitoring",
    description: "Video, comment va hashtag/kodli source oqimi.",
    metrics: (mentions, engagement, sources) => [
      { label: "Video", value: mentions.youtube_videos || 0 },
      { label: "Comment", value: mentions.youtube_comments || 0 },
      { label: "Like", value: engagement.youtube_likes || 0 },
      { label: "Official source", value: sources.official_youtube || 0 },
    ],
  },
  instagram: {
    key: "instagram",
    label: "Instagram",
    tone: "instagram",
    Icon: Instagram,
    href: "/instagram-monitoring",
    description: "Business akkaunt comment va @mention oqimi.",
    metrics: (mentions, engagement, sources) => [
      { label: "Comment", value: mentions.instagram_comments || 0 },
      { label: "@Mention", value: mentions.instagram_direct_mentions || 0 },
      { label: "Like", value: engagement.instagram_likes || 0 },
      { label: "Official source", value: sources.official_instagram || 0 },
    ],
  },
  facebook: {
    key: "facebook",
    label: "Facebook",
    tone: "facebook",
    Icon: Facebook,
    href: "/facebook-monitoring",
    description: "Page comment, reply va post mention oqimi.",
    metrics: (mentions, engagement, sources) => [
      { label: "Comment", value: mentions.facebook_comments || 0 },
      { label: "Reply", value: mentions.facebook_replies || 0 },
      { label: "Like", value: engagement.facebook_likes || 0 },
      { label: "Official source", value: sources.official_facebook || 0 },
    ],
  },
};

function PlatformChartCard({ platform, rows, period, mentions, engagement, sources }) {
  const config = platformCardConfig[platform] || platformCardConfig.telegram;
  const Icon = config.Icon;
  const series = { key: config.key, label: config.label, tone: config.tone };
  const metrics = config.metrics(mentions, engagement, sources);

  return (
    <article className={`dashboardPanel panel platformPanel ${series.tone}`}>
      <div className="sectionHeader compact">
        <div>
          <h2><Icon size={18} /> {series.label} holati</h2>
          <p>{config.description}</p>
        </div>
        <a className="miniButton linkButton" href={config.href}>
          <PlusCircle size={15} />
          <span>Manba</span>
        </a>
      </div>
      <SinglePlatformChart rows={rows} series={series} period={period} />
      <div className="platformMetricStrip">
        {metrics.map((item) => (
          <span key={item.label}>
            <em>{item.label}</em>
            <strong>{compactNumber(item.value)}</strong>
          </span>
        ))}
      </div>
    </article>
  );
}

function DashboardOperations({ mentions, sources, ai, forecast }) {
  const platformCount = ["telegram", "youtube", "instagram", "facebook"].filter((platform) => (mentions[platform] || sources[platform] || 0) > 0).length;
  const pendingAi = Math.max(0, (mentions.total || 0) - (ai.processed_mentions || 0));
  const metaReady = (sources.instagram || 0) + (sources.facebook || 0);
  const tokenIssue = sources.invalid_meta_tokens || 0;

  const rows = [
    {
      title: "Coverage nazorati",
      value: `${platformCount}/4`,
      text: "Brand signali nechta platformadan kelayotganini ko'rsatadi.",
      Icon: Activity,
      tone: "total",
    },
    {
      title: "AI navbati",
      value: compactNumber(pendingAi),
      text: pendingAi ? "Tahlil qilinmagan mentionlar bor, worker navbati tekshiriladi." : "Yangi mentionlar AI tahlildan o'tgan.",
      Icon: Brain,
      tone: "ai",
    },
    {
      title: "Meta tayyorgarlik",
      value: tokenIssue ? `${tokenIssue} token` : compactNumber(metaReady),
      text: tokenIssue
        ? "Instagram/Facebook tokenlaridan biri yaroqsiz. Avval token yangilanadi."
        : "Meta source mavjud bo'lsa poller/webhook orqali oqim kuzatiladi.",
      Icon: ShieldAlert,
      tone: tokenIssue ? "risk" : "source",
    },
    {
      title: "Action prognoz",
      value: compactNumber(forecast.next_7d_mentions || 0),
      text: "Keyingi 7 kunda kelishi mumkin bo'lgan mention hajmi.",
      Icon: TrendingUp,
      tone: "source",
    },
  ];

  return (
    <section className="dashboardOpsGrid">
      {rows.map((item) => (
        <article className={`opsPanel ${item.tone}`} key={item.title}>
          <span className="opsIcon"><item.Icon size={18} /></span>
          <div>
            <strong>{item.title}</strong>
            <b>{item.value}</b>
            <p>{item.text}</p>
          </div>
        </article>
      ))}
    </section>
  );
}

function SectionHeaderSkeleton({ pill = false } = {}) {
  return (
    <div className="sectionHeader skeletonHeader">
      <div>
        <span className="skeletonText heading" />
        <span className="skeletonText wide" />
      </div>
      {pill && <span className="skeletonPill" />}
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <>
      <section className="scopeStrip isLoading" aria-busy="true">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={`scope-skeleton-${index}`}>
            <span className="skeletonText sm" />
            <span className="skeletonText mid" />
          </div>
        ))}
      </section>

      <article className="dashboardPanel panel sourceSetupPanel isLoading" aria-busy="true">
        <SectionHeaderSkeleton pill />
        <div className="sourceSetupGrid">
          {Array.from({ length: 4 }).map((_, index) => (
            <div className="sourceSetupCard skeletonSetupCard" key={`setup-skeleton-${index}`}>
              <span className="skeletonIcon" />
              <span>
                <i className="skeletonText heading" />
                <i className="skeletonText sm" />
              </span>
              <i className="skeletonText xs" />
            </div>
          ))}
        </div>
      </article>

      <section className="analyticsHero">
        <article className="dashboardPanel panel isLoading" aria-busy="true">
          <SectionHeaderSkeleton pill />
          <div className="skeletonChart">
            <span />
            <span />
            <span />
          </div>
          <div className="chartSummary">
            {Array.from({ length: 4 }).map((_, index) => (
              <span key={`chart-summary-skeleton-${index}`}>
                <i className="skeletonText sm" />
                <i className="skeletonText value" />
              </span>
            ))}
          </div>
        </article>
        <article className="dashboardPanel panel forecastPanel isLoading" aria-busy="true">
          <div className="forecastTop">
            <div>
              <span className="skeletonText sm" />
              <span className="skeletonText heroValue" />
            </div>
            <span className="skeletonIcon lg" />
          </div>
          <div className="forecastGrid skeletonForecastGrid">
            {Array.from({ length: 10 }).map((_, index) => (
              <span className="skeletonText sm" key={`forecast-skeleton-${index}`} />
            ))}
          </div>
          <span className="skeletonText wide" />
        </article>
      </section>

      <section className="platformChartGrid">
        {Array.from({ length: 4 }).map((_, index) => (
          <article className="dashboardPanel panel platformPanel isLoading" aria-busy="true" key={`platform-chart-skeleton-${index}`}>
            <SectionHeaderSkeleton pill />
            <div className="skeletonChart compact">
              <span />
              <span />
              <span />
            </div>
            <div className="platformMetricStrip skeletonPlatformMetrics">
              {Array.from({ length: 4 }).map((__, itemIndex) => (
                <span key={`platform-metric-skeleton-${index}-${itemIndex}`} />
              ))}
            </div>
          </article>
        ))}
      </section>

      <section className="dashboardGrid">
        {Array.from({ length: 4 }).map((_, index) => (
          <article className="dashboardPanel panel isLoading" aria-busy="true" key={`panel-skeleton-${index}`}>
            <SectionHeaderSkeleton pill={index === 3} />
            <div className={index === 2 ? "metricGrid skeletonMetricGrid" : "barList compact skeletonBarList"}>
              {Array.from({ length: index === 2 ? 6 : 4 }).map((__, itemIndex) => (
                <span key={`panel-skeleton-row-${index}-${itemIndex}`} />
              ))}
            </div>
          </article>
        ))}
        <article className="dashboardPanel panel wide isLoading" aria-busy="true">
          <SectionHeaderSkeleton />
          <div className="riskLayout">
            <div className="distribution skeletonDistribution">
              <span />
              <span />
              <span />
            </div>
            <div className="aiPlan skeletonAiPlan">
              <span className="skeletonIcon" />
              <span className="skeletonText heading" />
              <span className="skeletonText wide" />
              <span className="skeletonText mid" />
            </div>
          </div>
        </article>
      </section>
    </>
  );
}

export function Dashboard() {
  const [botStatus, setBotStatus] = useState(null);
  const [brands, setBrands] = useState([]);
  const [selectedBrandId, setSelectedBrandId] = useState(() => readSelectedBrandId());
  const [periodKey, setPeriodKey] = useState("month");
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const lastLoadedDashboardKey = useRef("");
  const activePeriod = useMemo(
    () => periodOptions.find((item) => item.key === periodKey) || periodOptions[2],
    [periodKey],
  );

  const loadDashboard = useCallback(async (brandId = selectedBrandId, period = activePeriod) => {
    lastLoadedDashboardKey.current = `${brandId || ""}:${period.key}`;
    const analyticsRow = await endpoints.dashboardAnalytics(brandId || "", period.value, period.interval, browserTimezone);
    setAnalytics(analyticsRow);
  }, [activePeriod, selectedBrandId]);

  const loadInitial = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [bot, brandRows] = await Promise.all([endpoints.botStatus(), endpoints.brands()]);
      setBotStatus(bot);
      setBrands(brandRows);
      const nextBrandId = resolveSelectedBrandId(brandRows, selectedBrandId);
      if (nextBrandId && nextBrandId !== selectedBrandId) setSelectedBrandId(nextBrandId);
      await loadDashboard(nextBrandId, activePeriod);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [activePeriod, loadDashboard, selectedBrandId]);

  useEffect(() => {
    loadInitial();
  }, []);

  useEffect(() => {
    const dashboardKey = `${selectedBrandId || ""}:${activePeriod.key}`;
    if (dashboardKey === lastLoadedDashboardKey.current) return;
    loadDashboard(selectedBrandId, activePeriod).catch((err) => setError(err.message));
  }, [selectedBrandId, activePeriod, loadDashboard]);

  const mentions = analytics?.mentions || {};
  const sources = analytics?.sources || {};
  const engagement = analytics?.engagement || {};
  const forecast = analytics?.forecast || {};
  const ai = analytics?.ai || {};
  const filter = analytics?.filter || {};
  const highRisk = (analytics?.risk?.high || 0) + (analytics?.risk?.critical || 0);
  const TrendIcon = trendIcon(forecast.direction);
  const isInitialLoading = loading && !analytics;

  const statItems = [
    { label: "Source", value: sources.total || 0, icon: BarChart3, tone: "source" },
    { label: "Mention", value: mentions.total || 0, icon: MessageSquareText, tone: "total" },
    { label: "AI tahlil", value: mentions.analyzed || 0, icon: Brain, tone: "ai" },
    { label: "High risk", value: highRisk, icon: ShieldAlert, tone: "risk" },
  ];

  const platformRows = useMemo(
    () => [
      { label: "Telegram", value: mentions.telegram || 0, icon: TelegramIcon, tone: "telegram" },
      { label: "YouTube", value: mentions.youtube || 0, icon: YouTubeIcon, tone: "youtube" },
      { label: "Instagram", value: mentions.instagram || 0, icon: Instagram, tone: "instagram" },
      { label: "Facebook", value: mentions.facebook || 0, icon: Facebook, tone: "facebook" },
    ],
    [mentions.telegram, mentions.youtube, mentions.instagram, mentions.facebook],
  );

  const actionRows = useMemo(
    () => [
      { label: "Telegram post", value: mentions.telegram_posts || 0, tone: "telegram" },
      { label: "Telegram chat/comment", value: mentions.telegram_comments || 0, tone: "telegram" },
      { label: "YouTube video", value: mentions.youtube_videos || 0, tone: "youtube" },
      { label: "YouTube comment", value: mentions.youtube_comments || 0, tone: "youtube" },
      { label: "Instagram comment", value: mentions.instagram_comments || 0, tone: "instagram" },
      { label: "Instagram @mention", value: mentions.instagram_direct_mentions || 0, tone: "instagram" },
      { label: "Facebook comment", value: mentions.facebook_comments || 0, tone: "facebook" },
      { label: "Facebook reply", value: mentions.facebook_replies || 0, tone: "facebook" },
    ],
    [mentions],
  );

  const sentimentRows = Object.entries(analytics?.sentiment || {}).map(([key, value]) => ({
    key,
    label: sentimentLabels[key] || key,
    value,
  }));

  const riskRows = Object.entries(analytics?.risk || {}).map(([key, value]) => ({
    key,
    label: riskLabels[key] || key,
    value,
  }));

  return (
    <div className="appShell">
      <Sidebar botStatus={botStatus} activePath="/" />
      <main className="main">
        <PageHeader
          eyebrow="Brand intelligence"
          title="Umumiy dashboard"
          loading={isInitialLoading}
        />
        {error && <div className="errorBanner">{error}</div>}

        <div className="periodTabs" role="tablist" aria-label="Dashboard davri">
          {isInitialLoading
            ? periodOptions.map((item) => <span className="skeletonTab" key={item.key} />)
            : periodOptions.map((item) => (
                <button
                  key={item.key}
                  className={periodKey === item.key ? "active" : ""}
                  type="button"
                  onClick={() => setPeriodKey(item.key)}
                >
                  {item.label}
                </button>
              ))}
        </div>

        <StatsBar items={statItems} loading={isInitialLoading} />

        {isInitialLoading ? (
          <DashboardSkeleton />
        ) : (
          <>
        <section className="scopeStrip">
          <div>
            <span>Filter</span>
            <strong>{filter.scope || "Tanlangan brand/client bo'yicha"}</strong>
          </div>
          <div>
            <span>Brand</span>
            <strong>{filter.brand_name || "Barcha brandlar"}</strong>
          </div>
          <div>
            <span>AI ishonchlilik</span>
            <strong>{percent(ai.reliability || 0)}</strong>
            <small>{reliabilityDetail(ai)}</small>
          </div>
          <div>
            <span>AI qamrov</span>
            <strong>{percent(ai.total_coverage || 0)}</strong>
            <small>{platformCoverageDetail(ai)}</small>
          </div>
        </section>

        <OfficialSourceSetup sources={sources} filter={filter} />
        <DashboardOperations mentions={mentions} sources={sources} ai={ai} forecast={forecast} />

        <section className="analyticsHero">
          <article className="dashboardPanel panel">
            <div className="sectionHeader">
              <div>
                <h2>Brand harakati</h2>
                <p>Tanlangan brand va davr bo'yicha barcha platformalardagi mention oqimi.</p>
              </div>
              <span className="pill neutral">{activePeriod.label} · {intervalLabels[analytics?.period?.interval || activePeriod.interval]}</span>
            </div>
            <DashboardLineChart rows={analytics?.trend || []} period={analytics?.period || activePeriod} />
          </article>

          <article className={`dashboardPanel panel forecastPanel ${forecast.direction || "barqaror"}`}>
            <div className="forecastTop">
              <div>
                <span>Keyingi 7 kun prognozi</span>
                <strong>{compactNumber(forecast.next_7d_mentions || 0)}</strong>
              </div>
              <TrendIcon size={28} />
            </div>
            <div className="forecastGrid">
              <span>Trend</span>
              <strong>{forecast.direction || "barqaror"}</strong>
              <span>Oldingi davrga nisbatan</span>
              <strong>{changeLabel(forecast.change_percent || 0)}</strong>
              <span>Ishonch</span>
              <strong>{percent(forecast.confidence || 0)}</strong>
              <span>Comment/chat prognoz</span>
              <strong>{compactNumber(forecast.next_7d_comments)}</strong>
              <span>Like prognoz</span>
              <strong>{compactNumber(forecast.next_7d_youtube_likes)}</strong>
            </div>
            <p>{forecast.method}</p>
          </article>
        </section>

        <section className="platformChartGrid">
          <PlatformChartCard
            platform="telegram"
            rows={analytics?.trend || []}
            period={analytics?.period || activePeriod}
            mentions={mentions}
            engagement={engagement}
            sources={sources}
          />
          <PlatformChartCard
            platform="youtube"
            rows={analytics?.trend || []}
            period={analytics?.period || activePeriod}
            mentions={mentions}
            engagement={engagement}
            sources={sources}
          />
          <PlatformChartCard
            platform="instagram"
            rows={analytics?.trend || []}
            period={analytics?.period || activePeriod}
            mentions={mentions}
            engagement={engagement}
            sources={sources}
          />
          <PlatformChartCard
            platform="facebook"
            rows={analytics?.trend || []}
            period={analytics?.period || activePeriod}
            mentions={mentions}
            engagement={engagement}
            sources={sources}
          />
        </section>

        <section className="dashboardGrid">
          <article className="dashboardPanel panel">
            <div className="sectionHeader">
              <div>
                <h2>Engagement</h2>
                <p>Like, view, reaction va comment signalari hamda prognoz.</p>
              </div>
            </div>
            <div className="metricGrid">
              <div className="youtube"><Heart size={17} /><strong>{compactNumber(engagement.youtube_likes)}</strong><span>YouTube like</span></div>
              <div className="youtube"><Eye size={17} /><strong>{compactNumber(engagement.youtube_views)}</strong><span>YouTube view</span></div>
              <div className="telegram"><Activity size={17} /><strong>{compactNumber(engagement.telegram_reactions)}</strong><span>Telegram reaction</span></div>
              <div className="total"><MessageSquareText size={17} /><strong>{compactNumber(engagement.youtube_comment_count)}</strong><span>Video comment count</span></div>
              <div className="instagram"><Heart size={17} /><strong>{compactNumber(engagement.instagram_likes)}</strong><span>Instagram like</span></div>
              <div className="facebook"><MessageSquareText size={17} /><strong>{compactNumber(engagement.facebook_replies)}</strong><span>Facebook reply</span></div>
              <div className="youtube"><Heart size={17} /><strong>{compactNumber(forecast.next_7d_youtube_likes)}</strong><span>7 kun like prognoz</span></div>
              <div className="youtube"><Eye size={17} /><strong>{compactNumber(forecast.next_7d_youtube_views)}</strong><span>7 kun view prognoz</span></div>
            </div>
            <p className="mutedNote">{engagement.youtube_dislikes_note}</p>
          </article>

          <article className="dashboardPanel panel">
            <div className="sectionHeader">
              <div>
                <h2>Content turi</h2>
                <p>Post, video, chat va commentlar kesimi.</p>
              </div>
            </div>
            <ProgressRows rows={actionRows} />
          </article>

          <article className="dashboardPanel panel">
            <div className="sectionHeader">
              <div>
                <h2>Platformalar</h2>
                <p>Qaysi platformadan qancha signal kelmoqda.</p>
              </div>
            </div>
            <ProgressRows rows={platformRows} />
          </article>

          <article className="dashboardPanel panel">
            <div className="sectionHeader">
              <div>
                <h2>AI kayfiyat</h2>
                <p>Vertex/Gemini tahlil qilgan mentionlar asosida.</p>
              </div>
              <span className="pill neutral">{percent(mentions.analysis_coverage || 0)}</span>
            </div>
            <Distribution rows={sentimentRows} type="sentiment" />
            <div className="aiScoreGrid">
              <span>O'rtacha sentiment score <strong>{score(ai.avg_sentiment_score)}</strong></span>
              <span>O'rtacha risk score <strong>{score(ai.avg_risk_score)}</strong></span>
              <span>Model <strong>{ai.model || "Gemini"}</strong></span>
              <span>Platform qamrovi <strong>{platformCoverageDetail(ai)}</strong></span>
            </div>
            <p className="mutedNote">{ai.note}</p>
          </article>

          <article className="dashboardPanel panel wide">
            <div className="sectionHeader">
              <div>
                <h2>Risk va ustuvorlik</h2>
                <p>Brandga zarar yetkazishi mumkin bo'lgan signallar.</p>
              </div>
              <button className="button secondary" type="button" onClick={loadInitial}>
                <RefreshCw size={17} />
                <span>Yangilash</span>
              </button>
            </div>
            <div className="riskLayout">
              <Distribution rows={riskRows} type="risk" />
              <div className="aiPlan">
                <Sparkles size={20} />
                <strong>AI action layer</strong>
                <p>Dashboard mention hajmi, sentiment, risk va AI qamrovini birlashtirib ustuvor signalni ko'rsatadi. Salbiy yoki yuqori riskli xabarlar birinchi navbatda javobga chiqariladi.</p>
              </div>
            </div>
          </article>
        </section>
          </>
        )}
      </main>
    </div>
  );
}

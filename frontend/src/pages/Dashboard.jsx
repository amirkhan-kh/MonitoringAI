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
import { PercentGauge, PlatformShareChart, PlatformTrendChart } from "../components/TrendChart";
import { translateUiText, useUiLanguage } from "../i18n";

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

function platformCoverageDetail(ai, lng) {
  const platformLabels = {
    telegram: "Telegram",
    youtube: "YouTube",
    instagram: "Instagram",
    facebook: "Facebook",
  };
  const platforms = ai?.platforms || {};
  const rows = Object.entries(platforms)
    .filter(([, metric]) => (metric?.mentions || 0) > 0)
    .map(([platform, metric]) => {
      const name = translateUiText(platformLabels[platform] || platform, { lng });
      return `${name}: ${percent(metric.coverage || 0)}`;
    });
  return rows.length
    ? rows.join(" · ")
    : translateUiText("AI tahlil uchun mention yo'q", { lng });
}

function reliabilityDetail(ai, lng) {
  const failed = ai?.failed_mentions || 0;
  const processed = ai?.processed_mentions || 0;
  const balance = percent(ai?.platform_balance || 0);
  if (!processed) return translateUiText("Hali AI tahlil yo'q", { lng });
  return translateUiText(`Processed ${processed} · Xato ${failed} · Balans ${balance}`, { lng });
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

function DashboardLineChart({ rows, period, lng }) {
  const tt = (value) => translateUiText(value, { lng });
  const safeRows = rows || [];
  const totals = chartSeries.reduce((acc, series) => {
    acc[series.key] = safeRows.reduce((sum, row) => sum + (row[series.key] || 0), 0);
    return acc;
  }, {});
  const peak = safeRows.reduce(
    (best, row) => ((row.total || 0) > (best.total || 0) ? row : best),
    safeRows[0] || { total: 0, label: "-" },
  );
  const shareTotals = {
    telegram: totals.telegram || 0,
    youtube: totals.youtube || 0,
    instagram: totals.instagram || 0,
    facebook: totals.facebook || 0,
  };
  const intervalText = tt(intervalLabels[period?.interval] || "Kunlik");

  return (
    <div className="analyticsChart" aria-label={tt("Platforma ulushi diagrammasi")}>
      <PlatformShareChart totals={shareTotals} height={248} />
      <div className="chartLegend chartLegend--share">
        {chartSeries
          .filter((series) => series.key !== "total")
          .map((series) => (
            <span key={series.key} data-i18n-ignore="true">
              <i className={series.tone} /> {tt(series.label)}
            </span>
          ))}
        <span className="chartTimezone" data-i18n-ignore="true">
          {intervalText} · {period?.timezone || "Asia/Tashkent"} {period?.utc_offset || "+05:00"}
        </span>
      </div>
      <div className="chartSummary">
        <span className="total" data-i18n-ignore="true">{tt("Jami")} <strong>{compactNumber(totals.total)}</strong></span>
        <span className="telegram" data-i18n-ignore="true">{tt("Telegram")} <strong>{compactNumber(totals.telegram)}</strong></span>
        <span className="youtube" data-i18n-ignore="true">{tt("YouTube")} <strong>{compactNumber(totals.youtube)}</strong></span>
        <span className="instagram" data-i18n-ignore="true">{tt("Instagram")} <strong>{compactNumber(totals.instagram)}</strong></span>
        <span className="facebook" data-i18n-ignore="true">{tt("Facebook")} <strong>{compactNumber(totals.facebook)}</strong></span>
        <span data-i18n-ignore="true">{tt("Pik davr")} <strong>{peak.label || "-"}</strong> · {compactNumber(peak.total)}</span>
      </div>
    </div>
  );
}

function SinglePlatformChart({ rows, series, period, lng }) {
  const tt = (value) => translateUiText(value, { lng });
  const safeRows = rows || [];
  const total = safeRows.reduce((sum, row) => sum + (row[series.key] || 0), 0);
  const peak = safeRows.reduce(
    (best, row) => ((row[series.key] || 0) > (best[series.key] || 0) ? row : best),
    safeRows[0] || { [series.key]: 0, label: "-" },
  );
  const seriesLabel = tt(series.label);
  const intervalText = tt(intervalLabels[period?.interval] || "Kunlik");

  return (
    <div className="platformChart" aria-label={`${seriesLabel} ${tt("Trend")}`}>
      <PlatformTrendChart rows={safeRows} series={series} />
      <div className="platformChartMeta">
        <span data-i18n-ignore="true"><i className={series.tone} /> {intervalText}</span>
        <strong>{compactNumber(total)}</strong>
        <span data-i18n-ignore="true">{tt("Pik")}: {peak.label || "-"} · {compactNumber(peak[series.key] || 0)}</span>
      </div>
    </div>
  );
}

function ProgressRows({ rows, lng }) {
  const tt = (value) => translateUiText(value, { lng });
  const max = maxValue(rows);
  return (
    <div className="barList compact">
      {rows.map((item) => (
        <div className={`barRow ${item.tone || ""}`} key={item.label}>
          <span data-i18n-ignore="true">{item.icon ? <item.icon size={16} /> : null} {tt(item.label)}</span>
          <div className="barTrack">
            <i className={item.tone || ""} style={{ width: `${Math.max(4, (item.value / max) * 100)}%` }} />
          </div>
          <strong>{compactNumber(item.value)}</strong>
        </div>
      ))}
    </div>
  );
}

const sentimentIcons = {
  positive: TrendingUp,
  neutral: Activity,
  negative: TrendingDown,
  mixed: Sparkles,
  unknown: Activity,
};

const riskIcons = {
  low: ShieldAlert,
  medium: ShieldAlert,
  high: ShieldAlert,
  critical: ShieldAlert,
  unknown: Activity,
};

function Distribution({ rows, type, lng }) {
  const tt = (value) => translateUiText(value, { lng });
  const total = rows.reduce((sum, item) => sum + item.value, 0);
  if (!total) return <div className="empty" data-i18n-ignore="true">{tt("Hali AI tahlil natijasi yo'q")}</div>;
  const iconMap = type === "sentiment" ? sentimentIcons : riskIcons;

  return (
    <div className="distribution">
      <div className="distributionBar">
        {rows.map((item) => (
          <i
            key={item.key}
            className={`${type}-${item.key}`}
            style={{ width: `${Math.max(4, (item.value / total) * 100)}%` }}
            title={`${tt(item.label)}: ${item.value}`}
          />
        ))}
      </div>
      <div className="distributionList">
        {rows.map((item) => {
          const Icon = iconMap[item.key] || Activity;
          return (
            <span key={item.key} data-i18n-ignore="true">
              <i className={`${type}-${item.key}`} />
              <Icon size={13} strokeWidth={2} aria-hidden="true" />
              {tt(item.label)} <strong className="tabular-nums">{item.value}</strong>
            </span>
          );
        })}
      </div>
    </div>
  );
}

function OfficialSourceSetup({ sources, filter, lng }) {
  const tt = (value) => translateUiText(value, { lng });
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
          <h2 data-i18n-ignore="true">{tt("Official source")}</h2>
          <p data-i18n-ignore="true">
            {`${filter.brand_name || tt("Brand")} ${tt("rasmiy manbalari.")}`}
          </p>
        </div>
        <a className="button secondary linkButton" href="/profile">
          <ExternalLink size={16} />
          <span data-i18n-ignore="true">{tt("Profil")}</span>
        </a>
      </div>
      <div className="sourceSetupGrid">
        {platforms.map((item) => {
          const Icon = item.icon;
          return (
            <div className={`sourceSetupCard ${item.tone}`} key={item.label}>
              <span className="setupIcon"><Icon size={18} /></span>
              <span>
                <strong data-i18n-ignore="true">{tt(item.label)}</strong>
                <em data-i18n-ignore="true">{tt(item.description)}</em>
              </span>
              <b>{item.official}/{item.total}</b>
              <small data-i18n-ignore="true">{tt(item.status)}</small>
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

function PlatformChartCard({ platform, rows, period, mentions, engagement, sources, lng }) {
  const tt = (value) => translateUiText(value, { lng });
  const config = platformCardConfig[platform] || platformCardConfig.telegram;
  const Icon = config.Icon;
  const series = { key: config.key, label: config.label, tone: config.tone };
  const metrics = config.metrics(mentions, engagement, sources);

  return (
    <article className={`dashboardPanel panel platformPanel ${series.tone}`}>
      <div className="sectionHeader compact">
        <div>
          <h2 data-i18n-ignore="true"><Icon size={18} /> {tt(series.label)} {tt("holati")}</h2>
          <p data-i18n-ignore="true">{tt(config.description)}</p>
        </div>
        <a className="miniButton linkButton" href={config.href}>
          <PlusCircle size={15} />
          <span data-i18n-ignore="true">{tt("Manba")}</span>
        </a>
      </div>
      <SinglePlatformChart rows={rows} series={series} period={period} lng={lng} />
      <div className="platformMetricStrip">
        {metrics.map((item) => (
          <span key={item.label}>
            <em data-i18n-ignore="true">{tt(item.label)}</em>
            <strong>{compactNumber(item.value)}</strong>
          </span>
        ))}
      </div>
    </article>
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
  const lng = useUiLanguage();
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
      <Sidebar botStatus={botStatus} activePath="/umumiy-dashboard" />
      <main className="main">
        <PageHeader
          eyebrow="Brand intelligence"
          title="Umumiy dashboard"
          loading={isInitialLoading}
        />
        {error && <div className="errorBanner">{error}</div>}

        <div className="periodTabs" role="tablist" aria-label={translateUiText("Dashboard davri", { lng })}>
          {isInitialLoading
            ? periodOptions.map((item) => <span className="skeletonTab" key={item.key} />)
            : periodOptions.map((item) => (
                <button
                  key={item.key}
                  className={periodKey === item.key ? "active" : ""}
                  type="button"
                  onClick={() => setPeriodKey(item.key)}
                >
                  <span data-i18n-ignore="true">{translateUiText(item.label, { lng })}</span>
                </button>
              ))}
        </div>

        <StatsBar
          items={statItems.map((item) => ({ ...item, label: translateUiText(item.label, { lng }) }))}
          loading={isInitialLoading}
        />

        {isInitialLoading ? (
          <DashboardSkeleton />
        ) : (
          <>
        <section className="scopeStrip scopeStrip--gauges" aria-label={translateUiText("Filtr va AI sifat ko'rsatkichlari", { lng })}>
          <article className="scopeCard scopeCard--meta">
            <span className="scopeCardLabel" data-i18n-ignore="true">{translateUiText("Filter", { lng })}</span>
            <strong className="scopeCardValue" data-i18n-ignore="true">
              {translateUiText(filter.scope || "Tanlangan brand/client bo'yicha", { lng })}
            </strong>
            <p className="scopeCardHint" data-i18n-ignore="true">
              {translateUiText("Dashboard ma'lumotlari tanlangan brand doirasida.", { lng })}
            </p>
          </article>
          <article className="scopeCard scopeCard--meta">
            <span className="scopeCardLabel" data-i18n-ignore="true">{translateUiText("Brand", { lng })}</span>
            <strong className="scopeCardValue" data-i18n-ignore="true">
              {filter.brand_name || translateUiText("Barcha brandlar", { lng })}
            </strong>
            <p className="scopeCardHint" data-i18n-ignore="true">
              {translateUiText("Official source va mention oqimi shu brand bo'yicha.", { lng })}
            </p>
          </article>
          <article className="scopeCard scopeCard--gauge tone-violet">
            <div className="scopeCardHead">
              <span className="scopeCardLabel" data-i18n-ignore="true">{translateUiText("AI ishonchlilik", { lng })}</span>
              <span className="scopeCardBadge">{percent(ai.reliability || 0)}</span>
            </div>
            <PercentGauge
              value={ai.reliability || 0}
              max={100}
              height={120}
              tone="total"
              showTicks
              showLabels
            />
            <small className="scopeCardHint" data-i18n-ignore="true">{reliabilityDetail(ai, lng)}</small>
          </article>
          <article className="scopeCard scopeCard--gauge tone-teal">
            <div className="scopeCardHead">
              <span className="scopeCardLabel" data-i18n-ignore="true">{translateUiText("AI qamrov", { lng })}</span>
              <span className="scopeCardBadge">{percent(ai.total_coverage || 0)}</span>
            </div>
            <PercentGauge
              value={ai.total_coverage || 0}
              max={100}
              height={120}
              tone="positive"
              showTicks
              showLabels
            />
            <small className="scopeCardHint" data-i18n-ignore="true">{platformCoverageDetail(ai, lng)}</small>
          </article>
        </section>

        <OfficialSourceSetup sources={sources} filter={filter} lng={lng} />

        <section className="analyticsHero">
          <article className="dashboardPanel panel">
            <div className="sectionHeader">
              <div>
                <h2 data-i18n-ignore="true">{translateUiText("Platform ulushi", { lng })}</h2>
                <p data-i18n-ignore="true">
                  {translateUiText("Tanlangan brand va davr bo'yicha platformalar umumiy taqsimoti.", { lng })}
                </p>
              </div>
              <span className="pill neutral" data-i18n-ignore="true">
                {translateUiText(activePeriod.label, { lng })} ·{" "}
                {translateUiText(intervalLabels[analytics?.period?.interval || activePeriod.interval], { lng })}
              </span>
            </div>
            <DashboardLineChart
              rows={analytics?.trend || []}
              period={analytics?.period || activePeriod}
              lng={lng}
            />
          </article>

          <article className={`dashboardPanel panel forecastPanel ${forecast.direction || "barqaror"}`}>
            <div className="forecastTop">
              <div>
                <span data-i18n-ignore="true">{translateUiText("7 kun prognoz", { lng })}</span>
                <strong>{compactNumber(forecast.next_7d_mentions || 0)}</strong>
              </div>
              <TrendIcon size={28} />
            </div>
            <div className="forecastGrid">
              <span data-i18n-ignore="true">{translateUiText("Trend", { lng })}</span>
              <strong data-i18n-ignore="true">{translateUiText(forecast.direction || "barqaror", { lng })}</strong>
              <span data-i18n-ignore="true">{translateUiText("O'zgarish", { lng })}</span>
              <strong>{changeLabel(forecast.change_percent || 0)}</strong>
              <span data-i18n-ignore="true">{translateUiText("Ishonch", { lng })}</span>
              <strong>{percent(forecast.confidence || 0)}</strong>
              <span data-i18n-ignore="true">{translateUiText("Comment", { lng })}</span>
              <strong>{compactNumber(forecast.next_7d_comments)}</strong>
              <span data-i18n-ignore="true">{translateUiText("Like", { lng })}</span>
              <strong>{compactNumber(forecast.next_7d_youtube_likes)}</strong>
            </div>
            <p data-i18n-ignore={forecast.method ? "true" : undefined}>
              {forecast.method ? translateUiText(forecast.method, { lng }) : null}
            </p>
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
            lng={lng}
          />
          <PlatformChartCard
            platform="youtube"
            rows={analytics?.trend || []}
            period={analytics?.period || activePeriod}
            mentions={mentions}
            engagement={engagement}
            sources={sources}
            lng={lng}
          />
          <PlatformChartCard
            platform="instagram"
            rows={analytics?.trend || []}
            period={analytics?.period || activePeriod}
            mentions={mentions}
            engagement={engagement}
            sources={sources}
            lng={lng}
          />
          <PlatformChartCard
            platform="facebook"
            rows={analytics?.trend || []}
            period={analytics?.period || activePeriod}
            mentions={mentions}
            engagement={engagement}
            sources={sources}
            lng={lng}
          />
        </section>

        <section className="dashboardGrid">
          <article className="dashboardPanel panel">
            <div className="sectionHeader">
              <div>
                <h2 data-i18n-ignore="true">{translateUiText("Engagement", { lng })}</h2>
                <p data-i18n-ignore="true">
                  {translateUiText("Like, view, reaction va comment signalari hamda prognoz.", { lng })}
                </p>
              </div>
            </div>
            <div className="metricGrid">
              <div className="youtube"><Heart size={17} /><strong>{compactNumber(engagement.youtube_likes)}</strong><span data-i18n-ignore="true">{translateUiText("YouTube like", { lng })}</span></div>
              <div className="youtube"><Eye size={17} /><strong>{compactNumber(engagement.youtube_views)}</strong><span data-i18n-ignore="true">{translateUiText("YouTube view", { lng })}</span></div>
              <div className="telegram"><Activity size={17} /><strong>{compactNumber(engagement.telegram_reactions)}</strong><span data-i18n-ignore="true">{translateUiText("Telegram reaction", { lng })}</span></div>
              <div className="total"><MessageSquareText size={17} /><strong>{compactNumber(engagement.youtube_comment_count)}</strong><span data-i18n-ignore="true">{translateUiText("Video comment count", { lng })}</span></div>
              <div className="instagram"><Heart size={17} /><strong>{compactNumber(engagement.instagram_likes)}</strong><span data-i18n-ignore="true">{translateUiText("Instagram like", { lng })}</span></div>
              <div className="facebook"><MessageSquareText size={17} /><strong>{compactNumber(engagement.facebook_replies)}</strong><span data-i18n-ignore="true">{translateUiText("Facebook reply", { lng })}</span></div>
              <div className="youtube"><Heart size={17} /><strong>{compactNumber(forecast.next_7d_youtube_likes)}</strong><span data-i18n-ignore="true">{translateUiText("7 kun like prognoz", { lng })}</span></div>
              <div className="youtube"><Eye size={17} /><strong>{compactNumber(forecast.next_7d_youtube_views)}</strong><span data-i18n-ignore="true">{translateUiText("7 kun view prognoz", { lng })}</span></div>
            </div>
            <p className="mutedNote" data-i18n-ignore={engagement.youtube_dislikes_note ? "true" : undefined}>
              {engagement.youtube_dislikes_note
                ? translateUiText(engagement.youtube_dislikes_note, { lng })
                : null}
            </p>
          </article>

          <article className="dashboardPanel panel">
            <div className="sectionHeader">
              <div>
                <h2 data-i18n-ignore="true">{translateUiText("Content turi", { lng })}</h2>
                <p data-i18n-ignore="true">{translateUiText("Post, video, chat va commentlar kesimi.", { lng })}</p>
              </div>
            </div>
            <ProgressRows rows={actionRows} lng={lng} />
          </article>

          <article className="dashboardPanel panel">
            <div className="sectionHeader">
              <div>
                <h2 data-i18n-ignore="true">{translateUiText("Platformalar", { lng })}</h2>
                <p data-i18n-ignore="true">{translateUiText("Qaysi platformadan qancha signal kelmoqda.", { lng })}</p>
              </div>
            </div>
            <ProgressRows rows={platformRows} lng={lng} />
          </article>

          <article className="dashboardPanel panel">
            <div className="sectionHeader">
              <div>
                <h2 data-i18n-ignore="true">{translateUiText("AI kayfiyat", { lng })}</h2>
                <p data-i18n-ignore="true">{translateUiText("Vertex/Gemini tahlil qilgan mentionlar asosida.", { lng })}</p>
              </div>
              <span className="pill neutral">{percent(mentions.analysis_coverage || 0)}</span>
            </div>
            <Distribution rows={sentimentRows} type="sentiment" lng={lng} />
            <div className="aiScoreGrid">
              <span data-i18n-ignore="true">{translateUiText("O'rtacha sentiment score", { lng })} <strong>{score(ai.avg_sentiment_score)}</strong></span>
              <span data-i18n-ignore="true">{translateUiText("O'rtacha risk score", { lng })} <strong>{score(ai.avg_risk_score)}</strong></span>
              <span data-i18n-ignore="true">{translateUiText("Model", { lng })} <strong>{ai.model || "Gemini"}</strong></span>
              <span data-i18n-ignore="true">{translateUiText("Platform qamrovi", { lng })} <strong>{platformCoverageDetail(ai, lng)}</strong></span>
            </div>
            <p className="mutedNote" data-i18n-ignore={ai.note ? "true" : undefined}>
              {ai.note ? translateUiText(ai.note, { lng }) : null}
            </p>
          </article>

          <article className="dashboardPanel panel wide">
            <div className="sectionHeader">
              <div>
                <h2 data-i18n-ignore="true">{translateUiText("Risk va ustuvorlik", { lng })}</h2>
                <p data-i18n-ignore="true">{translateUiText("Brandga zarar yetkazishi mumkin bo'lgan signallar.", { lng })}</p>
              </div>
              <button className="button secondary" type="button" onClick={loadInitial}>
                <RefreshCw size={17} />
                <span data-i18n-ignore="true">{translateUiText("Yangilash", { lng })}</span>
              </button>
            </div>
            <div className="riskLayout">
              <Distribution rows={riskRows} type="risk" lng={lng} />
              <div className="aiPlan">
                <Sparkles size={20} />
                <strong data-i18n-ignore="true">{translateUiText("AI action layer", { lng })}</strong>
                <p data-i18n-ignore="true">
                  {translateUiText(
                    "Dashboard mention hajmi, sentiment, risk va AI qamrovini birlashtirib ustuvor signalni ko'rsatadi. Salbiy yoki yuqori riskli xabarlar birinchi navbatda javobga chiqariladi.",
                    { lng },
                  )}
                </p>
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

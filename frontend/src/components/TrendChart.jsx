/**
 * ECharts trend charts (Apache ECharts — free, Apache-2.0).
 *
 * Charts:
 *   - MentionTrendChart / PlatformTrendChart — time-series area
 *   - PlatformShareChart — pictorialBar peaks + platform logos (overall share)
 *   - PercentGauge / PipelineGauge — semicircle gauges
 *
 * Colors from CSS tokens via getComputedStyle; re-read on data-theme flip.
 * Chart type map: docs/01-planning/echarts-migration.md
 */
import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import i18n from "i18next";
import { translateUiText, useUiLanguage } from "../i18n";

const compact = (value) =>
  new Intl.NumberFormat("uz-UZ", { notation: "compact", maximumFractionDigits: 1 }).format(value || 0);

const tt = (value, lng, options = {}) => {
  if (options && Object.keys(options).length) {
    return i18n.t(value, { lng, defaultValue: value, ...options });
  }
  return translateUiText(value, { lng });
};

/** Resolve chart colors from CSS tokens; re-resolve on theme change. */
function useChartColors() {
  const [mode, setMode] = useState(
    () => (typeof document !== "undefined" && document.documentElement.dataset.theme) || "dark",
  );
  useEffect(() => {
    const el = document.documentElement;
    const observer = new MutationObserver(() => setMode(el.dataset.theme || "dark"));
    observer.observe(el, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);
  return useMemo(() => {
    const cs = getComputedStyle(document.documentElement);
    const read = (name, fallback) => cs.getPropertyValue(name).trim() || fallback;
    return {
      mode,
      areaFrom: read("--chart-area-from", "rgba(124,131,255,0.55)"),
      areaMid: read("--chart-area-mid", "rgba(124,131,255,0.18)"),
      areaTo: read("--chart-area-to", "rgba(124,131,255,0)"),
      line: read("--chart-line", "#8b8fff"),
      total: read("--chart-total", "#9f86ff"),
      grid: read("--chart-grid", "rgba(255,255,255,0.06)"),
      axis: read("--chart-axis", "#6b7280"),
      ink: read("--text", "#f2f3f5"),
      muted: read("--text-muted", "#a2a7b0"),
      accent: read("--accent", "#7c83ff"),
      warning: read("--warning", "#fbbf24"),
      telegram: read("--telegram", "#2aabee"),
      youtube: read("--youtube", "#ff3040"),
      instagram: read("--instagram", "#e4405f"),
      facebook: read("--facebook", "#1877f2"),
      positive: read("--positive", "#2dd4bf"),
      negative: read("--negative", "#fb7185"),
      tooltipBg: read("--chart-tooltip-bg", "rgba(26,27,32,0.96)"),
      tooltipInk: read("--chart-tooltip-ink", "#f2f3f5"),
    };
  }, [mode]);
}

/** Parse #rgb / #rrggbb / rgb() / rgba() → {r,g,b}. */
function parseColor(color) {
  if (!color) return null;
  const c = color.trim();
  if (c.startsWith("#")) {
    let hex = c.slice(1);
    if (hex.length === 3) hex = hex.split("").map((ch) => ch + ch).join("");
    if (hex.length < 6) return null;
    return {
      r: parseInt(hex.slice(0, 2), 16),
      g: parseInt(hex.slice(2, 4), 16),
      b: parseInt(hex.slice(4, 6), 16),
    };
  }
  const m = c.match(/rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)/i);
  if (m) return { r: +m[1], g: +m[2], b: +m[3] };
  return null;
}

/**
 * Soften vivid red / amber so gauges don't look "neon" on dark UI.
 * Mixes toward cool slate and slightly lowers brightness + adds soft tint.
 */
function softenHarsh(color, strength = 0.34) {
  const p = parseColor(color);
  if (!p) return color;
  const slate = { r: 88, g: 94, b: 108 };
  let r = p.r * (1 - strength) + slate.r * strength;
  let g = p.g * (1 - strength) + slate.g * strength;
  let b = p.b * (1 - strength) + slate.b * strength;
  const dim = 0.88;
  r = Math.round(r * dim);
  g = Math.round(g * dim);
  b = Math.round(b * dim);
  return `rgb(${r}, ${g}, ${b})`;
}

/** Soft fill for arcs (less pure, more design-system). */
function softArcColor(color, lighten = 0) {
  const p = parseColor(color);
  if (!p) return color;
  const r = Math.min(255, Math.round(p.r + (255 - p.r) * lighten));
  const g = Math.min(255, Math.round(p.g + (255 - p.g) * lighten));
  const b = Math.min(255, Math.round(p.b + (255 - p.b) * lighten));
  return `rgb(${r}, ${g}, ${b})`;
}

/** Map tone name → chart color from tokens (harsh hues softened). */
function toneColor(c, tone = "accent") {
  const map = {
    accent: c.accent,
    total: c.total,
    line: c.line,
    positive: c.positive,
    warning: softenHarsh(c.warning, 0.36),
    negative: softenHarsh(c.negative, 0.38),
    telegram: c.telegram,
    youtube: softenHarsh(c.youtube, 0.4),
    instagram: softenHarsh(c.instagram, 0.32),
    facebook: c.facebook,
    cyan: c.telegram,
    violet: c.total,
  };
  return map[tone] || c.accent;
}

/**
 * Semicircle percent gauge (ECharts) — temperature-gauge detail:
 * outer tick marks, major splits, numeric labels, soft arc gradient + shadow.
 * value: 0–100 (or 0–1 if max is 100 and value ≤ 1.5)
 */
export function PercentGauge({
  value = 0,
  max = 100,
  height = 118,
  tone = "accent",
  color,
  colorEnd,
  label = "",
  unit = "%",
  decimals = 0,
  showTicks = true,
  showLabels = true,
  compact = false,
}) {
  const c = useChartColors();
  const lng = useUiLanguage();
  const gaugeLabel = label ? tt(label, lng) : "";
  const rawPrimary = color || toneColor(c, tone);
  const harsh = tone === "warning" || tone === "negative" || tone === "youtube" || tone === "instagram";
  const primary = harsh && !color ? rawPrimary : harsh ? softenHarsh(rawPrimary, 0.3) : rawPrimary;
  const secondary = colorEnd
    ? harsh
      ? softenHarsh(colorEnd, 0.28)
      : colorEnd
    : softArcColor(primary, 0.12);

  const option = useMemo(() => {
    const safeMax = max > 0 ? max : 100;
    let raw = Number(value) || 0;
    if (safeMax === 100 && raw > 0 && raw <= 1.5) raw *= 100;
    const progress = Math.max(0, Math.min(safeMax, raw));
    const ratio = progress / safeMax;
    const track = withAlpha(c.axis, c.mode === "light" ? 0.16 : 0.2);
    const arcW = compact ? 10 : 12;
    const fontMain = compact ? 17 : 22;
    const fontUnit = compact ? 10 : 12;
    // Temperature-style: more splits → denser ticks + readable numbers
    const splits = compact ? 5 : 10;
    const tickColor = withAlpha(c.axis, c.mode === "light" ? 0.42 : 0.48);
    const majorColor = withAlpha(c.axis, c.mode === "light" ? 0.55 : 0.62);
    const labelColor = withAlpha(c.axis, c.mode === "light" ? 0.72 : 0.78);

    return {
      animationDuration: 1000,
      animationEasing: "cubicOut",
      animationDurationUpdate: 850,
      animationEasingUpdate: "cubicInOut",
      series: [
        {
          type: "gauge",
          startAngle: 200,
          endAngle: -20,
          min: 0,
          max: safeMax,
          splitNumber: splits,
          radius: compact ? "96%" : "100%",
          center: ["50%", compact ? "58%" : "60%"],
          axisLine: {
            roundCap: true,
            lineStyle: {
              width: arcW,
              shadowBlur: 14,
              shadowColor: withAlpha(primary, 0.35),
              shadowOffsetY: 2,
              color: [
                [
                  Math.max(0.001, ratio),
                  {
                    type: "linear",
                    x: 0,
                    y: 0,
                    x2: 1,
                    y2: 0,
                    colorStops: [
                      { offset: 0, color: withAlpha(primary, 0.82) },
                      { offset: 0.45, color: primary },
                      { offset: 1, color: withAlpha(secondary, 0.95) },
                    ],
                  },
                ],
                [1, track],
              ],
            },
          },
          progress: { show: false },
          pointer: { show: false },
          anchor: { show: false },
          axisTick: showTicks
            ? {
                show: true,
                // Outside the arc (temperature gauge style)
                distance: -(arcW + 3),
                length: compact ? 4 : 5,
                splitNumber: 5,
                lineStyle: { color: tickColor, width: 1 },
              }
            : { show: false },
          splitLine: showTicks
            ? {
                show: true,
                distance: -(arcW + 3),
                length: compact ? 8 : 11,
                lineStyle: { color: majorColor, width: 1.5 },
              }
            : { show: false },
          axisLabel: showLabels && showTicks
            ? {
                show: true,
                distance: compact ? 10 : 14,
                color: labelColor,
                fontSize: compact ? 8 : 10,
                fontWeight: 650,
                formatter: (v) => {
                  const n = Math.round(Number(v));
                  // Avoid label clutter on tiny gauges: every major split
                  return String(n);
                },
              }
            : { show: false },
          detail: {
            valueAnimation: true,
            offsetCenter: [0, compact ? "2%" : "4%"],
            formatter: (v) => {
              const n = Number(v);
              const text = decimals > 0 ? n.toFixed(decimals) : String(Math.round(n));
              return `{val|${text}}{unit|${unit}}`;
            },
            rich: {
              val: {
                fontSize: fontMain,
                fontWeight: 720,
                color: withAlpha(primary, 0.95),
                fontFamily: "Inter Variable, Inter, system-ui, sans-serif",
                padding: [0, 1, 0, 0],
                textShadowColor: withAlpha(primary, 0.45),
                textShadowBlur: 16,
                textShadowOffsetY: 1,
              },
              unit: {
                fontSize: fontUnit,
                fontWeight: 650,
                color: withAlpha(primary, 0.82),
                padding: [5, 0, 0, 2],
                textShadowColor: withAlpha(primary, 0.25),
                textShadowBlur: 8,
              },
            },
          },
          title: gaugeLabel
            ? {
                show: true,
                offsetCenter: [0, compact ? "34%" : "38%"],
                color: c.muted,
                fontSize: compact ? 10 : 11,
                fontWeight: 650,
              }
            : { show: false },
          data: [{ value: progress, name: gaugeLabel }],
        },
      ],
    };
  }, [
    c,
    compact,
    decimals,
    gaugeLabel,
    max,
    primary,
    secondary,
    showLabels,
    showTicks,
    unit,
    value,
  ]);

  return (
    <div className={`chartShell chartShell--gauge${compact ? " isCompact" : ""}`}>
      <ReactECharts
        option={option}
        style={{ height, width: "100%" }}
        opts={{ renderer: "canvas" }}
        notMerge
        lazyUpdate
      />
    </div>
  );
}

/**
 * Multi-step pipeline arc — how far the signal chain is ready (0–steps).
 * steps: string[] labels; activeCount: number of completed stages.
 */
export function PipelineGauge({ steps = [], activeCount = 0, height = 100, tone = "accent" }) {
  const c = useChartColors();
  const primary = toneColor(c, tone);
  const total = Math.max(1, steps.length);
  const active = Math.max(0, Math.min(total, activeCount));
  const pct = Math.round((active / total) * 100);

  const option = useMemo(() => {
    const track = withAlpha(c.axis, c.mode === "light" ? 0.16 : 0.2);
    const tickColor = withAlpha(c.axis, 0.45);
    return {
      animationDuration: 800,
      series: [
        {
          type: "gauge",
          startAngle: 200,
          endAngle: -20,
          min: 0,
          max: 100,
          splitNumber: Math.max(2, total),
          radius: "96%",
          center: ["50%", "58%"],
          axisLine: {
            roundCap: true,
            lineStyle: {
              width: 10,
              shadowBlur: 12,
              shadowColor: withAlpha(primary, 0.3),
              color: [
                [
                  Math.max(0.001, pct / 100),
                  {
                    type: "linear",
                    x: 0,
                    y: 0,
                    x2: 1,
                    y2: 0,
                    colorStops: [
                      { offset: 0, color: withAlpha(primary, 0.75) },
                      { offset: 1, color: primary },
                    ],
                  },
                ],
                [1, track],
              ],
            },
          },
          pointer: { show: false },
          axisTick: {
            show: true,
            distance: -13,
            length: 4,
            splitNumber: 2,
            lineStyle: { color: tickColor, width: 1 },
          },
          splitLine: {
            show: true,
            distance: -13,
            length: 8,
            lineStyle: { color: withAlpha(c.axis, 0.55), width: 1.4 },
          },
          axisLabel: {
            show: true,
            distance: 10,
            color: withAlpha(c.axis, 0.75),
            fontSize: 8,
            fontWeight: 650,
            formatter: (v) => String(Math.round(v)),
          },
          detail: {
            valueAnimation: true,
            offsetCenter: [0, "2%"],
            formatter: () => `{val|${active}}{sep|/}{tot|${total}}`,
            rich: {
              val: {
                fontSize: 20,
                fontWeight: 720,
                color: withAlpha(primary, 0.95),
                fontFamily: "Inter Variable, Inter, system-ui, sans-serif",
                textShadowColor: withAlpha(primary, 0.4),
                textShadowBlur: 12,
              },
              sep: { fontSize: 12, color: c.muted, padding: [4, 2, 0, 2] },
              tot: { fontSize: 13, fontWeight: 650, color: withAlpha(primary, 0.9), padding: [4, 0, 0, 0] },
            },
          },
          title: { show: false },
          data: [{ value: pct }],
        },
      ],
    };
  }, [active, c, pct, primary, total]);

  return (
    <div className="chartShell chartShell--gauge isCompact">
      <ReactECharts
        option={option}
        style={{ height, width: "100%" }}
        opts={{ renderer: "canvas" }}
        notMerge
        lazyUpdate
      />
    </div>
  );
}

/** SVG path data for platform logos (viewBox 0 0 24 24). */
const PLATFORM_LOGO_PATHS = {
  telegram:
    "M21.9 4.1 18.7 19c-.2 1-.8 1.3-1.6.8l-4.8-3.5-2.3 2.2c-.3.3-.5.5-1 .5l.4-4.9 8.9-8c.4-.4-.1-.6-.6-.2L6.6 12.8 1.9 11.3c-1-.3-1-1 .2-1.5L20.5 2.7c.8-.3 1.6.2 1.4 1.4Z",
  youtube:
    "M21.6 7.2a3 3 0 0 0-2.1-2.1C17.6 4.6 12 4.6 12 4.6s-5.6 0-7.5.5a3 3 0 0 0-2.1 2.1C1.9 9.1 1.9 12 1.9 12s0 2.9.5 4.8a3 3 0 0 0 2.1 2.1c1.9.5 7.5.5 7.5.5s5.6 0 7.5-.5a3 3 0 0 0 2.1-2.1c.5-1.9.5-4.8.5-4.8s0-2.9-.5-4.8ZM10 15.4V8.6l5.8 3.4-5.8 3.4Z",
  instagram:
    "M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z",
  facebook:
    "M22 12c0-5.52-4.48-10-10-10S2 6.48 2 12c0 4.84 3.44 8.87 8 9.8V15H8v-3h2V9.5C10 7.57 11.57 6 13.5 6H16v3h-2c-.55 0-1 .45-1 1v2h3v3h-3v6.95c5.05-.5 9-4.76 9-9.95z",
};

/** Soft mountain peak path for pictorialBar (ECharts “velocity / reindeer” style). */
const PEAK_SYMBOL =
  "path://M0,10 L10,10 C5.5,10 5.5,5 5,0 C4.5,5 4.5,10 0,10 z";

function logoDataUri(platform, color) {
  const d = PLATFORM_LOGO_PATHS[platform];
  if (!d) return "";
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="48" height="48">` +
    `<path fill="${color}" d="${d}"/></svg>`;
  return `image://data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

/**
 * Platform share pictorial chart — overall (not time-series).
 * Style: ECharts pictorialBar peaks with platform logos on top
 * (like “Velocity of Christmas Reindeer”, but TG/YT/IG/FB).
 *
 * totals: { telegram, youtube, instagram, facebook } absolute counts
 * OR rows: trend rows → summed per platform
 */
export function PlatformShareChart({ totals, rows, height = 268 }) {
  const c = useChartColors();
  const lng = useUiLanguage();

  const items = useMemo(() => {
    const sumKey = (key) => {
      if (totals && typeof totals[key] === "number") return Math.max(0, totals[key] || 0);
      return (rows || []).reduce((s, row) => s + (Number(row?.[key]) || 0), 0);
    };
    const palette = {
      telegram: c.telegram,
      youtube: softenHarsh(c.youtube, 0.42),
      instagram: softenHarsh(c.instagram, 0.3),
      facebook: c.facebook,
    };
    const list = [
      { key: "telegram", label: tt("Telegram", lng), value: sumKey("telegram"), color: palette.telegram },
      { key: "youtube", label: tt("YouTube", lng), value: sumKey("youtube"), color: palette.youtube },
      { key: "instagram", label: tt("Instagram", lng), value: sumKey("instagram"), color: palette.instagram },
      { key: "facebook", label: tt("Facebook", lng), value: sumKey("facebook"), color: palette.facebook },
    ]
      .map((item) => ({
        ...item,
        display: item.value,
      }))
      .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label));
    return list;
  }, [c.facebook, c.instagram, c.telegram, c.youtube, lng, rows, totals]);

  const option = useMemo(() => {
    const maxVal = Math.max(1, ...items.map((i) => i.value));
    // Give zero values a small visual floor so logos still sit above baseline
    const visual = items.map((i) => (i.value > 0 ? i.value : maxVal * 0.035));
    const labels = items.map((i) => i.label);

    return {
      animationDuration: 900,
      animationEasing: "cubicOut",
      grid: {
        left: 8,
        right: 8,
        top: 48,
        bottom: 28,
        containLabel: false,
      },
      tooltip: {
        trigger: "item",
        backgroundColor: c.tooltipBg,
        borderColor: "transparent",
        textStyle: { color: c.tooltipInk, fontSize: 12 },
        formatter(params) {
          const item = items[params.dataIndex];
          if (!item) return "";
          return (
            `<div style="display:flex;align-items:center;gap:8px">` +
            `<span style="width:8px;height:8px;border-radius:999px;background:${item.color}"></span>` +
            `<span style="flex:1;padding-right:12px">${item.label}</span>` +
            `<span style="font-weight:700;font-variant-numeric:tabular-nums">${compact(item.value)}</span>` +
            `</div>`
          );
        },
      },
      xAxis: {
        type: "category",
        data: labels,
        axisTick: { show: false },
        axisLine: { show: false },
        axisLabel: {
          color: c.muted,
          fontSize: 11,
          fontWeight: 650,
          margin: 12,
        },
      },
      yAxis: {
        type: "value",
        show: false,
        max: maxVal * 1.18,
        min: 0,
      },
      series: [
        // Soft peak mountains (body)
        {
          type: "pictorialBar",
          name: "ulush",
          symbol: PEAK_SYMBOL,
          symbolSize: ["54%", "100%"],
          barCategoryGap: "28%",
          z: 10,
          data: items.map((item, index) => ({
            value: visual[index],
            itemStyle: {
              color: {
                type: "linear",
                x: 0,
                y: 0,
                x2: 0,
                y2: 1,
                colorStops: [
                  { offset: 0, color: withAlpha(item.color, 0.92) },
                  { offset: 0.55, color: withAlpha(item.color, 0.42) },
                  { offset: 1, color: withAlpha(item.color, 0.08) },
                ],
              },
            },
          })),
        },
        // Platform logos perched on peaks
        {
          type: "pictorialBar",
          name: "logo",
          symbolPosition: "end",
          symbolSize: 26,
          symbolOffset: [0, "-118%"],
          z: 20,
          tooltip: { show: false },
          data: items.map((item, index) => ({
            value: visual[index],
            symbol: logoDataUri(item.key, item.color),
          })),
        },
        // Invisible value labels under logos
        {
          type: "pictorialBar",
          name: "value",
          symbolPosition: "end",
          symbolSize: 1,
          symbolOffset: [0, "-200%"],
          z: 15,
          label: {
            show: true,
            position: "top",
            distance: 28,
            formatter: (p) => compact(items[p.dataIndex]?.value || 0),
            color: c.ink,
            fontSize: 12,
            fontWeight: 720,
            fontFamily: "Inter Variable, Inter, system-ui, sans-serif",
          },
          tooltip: { show: false },
          data: visual.map((v) => ({ value: v, itemStyle: { color: "transparent" }, symbol: "circle" })),
        },
      ],
    };
  }, [c.ink, c.muted, c.tooltipBg, c.tooltipInk, items]);

  return (
    <div className="chartShell chartShell--share" aria-label={tt("Platforma ulushi", lng)}>
      <ReactECharts
        option={option}
        style={{ height, width: "100%" }}
        opts={{ renderer: "canvas" }}
        notMerge
        lazyUpdate
      />
    </div>
  );
}

function normalize(rows) {
  return (rows || []).map((row) => ({ ...row, label: row.label || row.bucket || "" }));
}

function baseGrid(extra = {}) {
  return {
    left: 8,
    right: 12,
    top: 16,
    bottom: 8,
    containLabel: true,
    ...extra,
  };
}

/** Main chart: smooth gradient area wave (total). Platform breakdown in tooltip. */
export function MentionTrendChart({ rows, height = 268 }) {
  const c = useChartColors();
  const lng = useUiLanguage();
  const data = useMemo(() => normalize(rows), [rows]);

  const option = useMemo(() => {
    const labels = data.map((d) => d.label);
    const totals = data.map((d) => Number(d.total) || 0);
    const nameJami = tt("Jami", lng);
    return {
      animationDuration: 750,
      grid: baseGrid({ top: 20, bottom: 4 }),
      tooltip: {
        trigger: "axis",
        backgroundColor: c.tooltipBg,
        borderColor: "transparent",
        textStyle: { color: c.tooltipInk, fontSize: 12 },
        axisPointer: {
          type: "line",
          lineStyle: { color: c.total, width: 1, opacity: 0.4 },
        },
        formatter(params) {
          const p = params?.[0];
          if (!p) return "";
          const row = data[p.dataIndex] || {};
          const items = [
            { key: "total", name: nameJami, color: c.total },
            { key: "telegram", name: tt("Telegram", lng), color: c.telegram },
            { key: "youtube", name: tt("YouTube", lng), color: c.youtube },
            { key: "instagram", name: tt("Instagram", lng), color: c.instagram },
            { key: "facebook", name: tt("Facebook", lng), color: c.facebook },
          ].filter((item) => item.key === "total" || (row[item.key] ?? 0) > 0);
          const lines = items
            .map(
              (item) =>
                `<div style="display:flex;align-items:center;gap:8px;margin-top:3px">` +
                `<span style="width:8px;height:8px;border-radius:999px;background:${item.color};flex-shrink:0"></span>` +
                `<span style="flex:1;padding-right:12px">${item.name}</span>` +
                `<span style="font-weight:700;font-variant-numeric:tabular-nums">${compact(row[item.key])}</span>` +
                `</div>`,
            )
            .join("");
          return `<div style="opacity:.7;margin-bottom:2px">${p.axisValueLabel || p.name || ""}</div>${lines}`;
        },
      },
      xAxis: {
        type: "category",
        data: labels,
        boundaryGap: false,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: c.axis, fontSize: 11, margin: 12, hideOverlap: true },
      },
      yAxis: {
        type: "value",
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: c.grid, type: [4, 7] } },
        axisLabel: {
          color: c.axis,
          fontSize: 11,
          formatter: (v) => compact(v),
        },
      },
      series: [
        {
          name: nameJami,
          type: "line",
          smooth: true,
          symbol: "circle",
          showSymbol: false,
          symbolSize: 8,
          data: totals,
          lineStyle: { width: 2.8, color: c.total },
          itemStyle: { color: c.total },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: withAlpha(c.total, 0.55) },
                { offset: 0.55, color: withAlpha(c.total, 0.16) },
                { offset: 1, color: withAlpha(c.total, 0) },
              ],
            },
          },
          emphasis: { focus: "series" },
        },
      ],
    };
  }, [c, data, lng]);

  return (
    <div className="chartShell chartShell--hero">
      <ReactECharts
        option={option}
        style={{ height, width: "100%" }}
        opts={{ renderer: "canvas" }}
        notMerge
        lazyUpdate
      />
    </div>
  );
}

/** Compact single-platform sparkline-style gradient area. */
export function PlatformTrendChart({ rows, series, height = 132 }) {
  const c = useChartColors();
  const lng = useUiLanguage();
  const data = useMemo(() => normalize(rows), [rows]);
  const color = c[series?.tone] || c.line;
  const key = series?.key || "total";
  const seriesLabel = tt(series?.label || key, lng);

  const option = useMemo(() => {
    const labels = data.map((d) => d.label);
    const values = data.map((d) => Number(d[key]) || 0);
    return {
      animationDuration: 650,
      grid: { left: 6, right: 6, top: 10, bottom: 0, containLabel: false },
      tooltip: {
        trigger: "axis",
        backgroundColor: c.tooltipBg,
        borderColor: "transparent",
        textStyle: { color: c.tooltipInk, fontSize: 12 },
        axisPointer: {
          type: "line",
          lineStyle: { color, width: 1, opacity: 0.35 },
        },
        formatter(params) {
          const p = params?.[0];
          if (!p) return "";
          return (
            `<div style="opacity:.7;margin-bottom:2px">${p.axisValueLabel || p.name || ""}</div>` +
            `<div style="display:flex;align-items:center;gap:8px;margin-top:3px">` +
            `<span style="width:8px;height:8px;border-radius:999px;background:${color};flex-shrink:0"></span>` +
            `<span style="flex:1;padding-right:12px">${seriesLabel}</span>` +
            `<span style="font-weight:700;font-variant-numeric:tabular-nums">${compact(p.value)}</span>` +
            `</div>`
          );
        },
      },
      xAxis: {
        type: "category",
        data: labels,
        boundaryGap: false,
        show: false,
      },
      yAxis: {
        type: "value",
        show: false,
        scale: false,
        min: 0,
      },
      series: [
        {
          name: seriesLabel,
          type: "line",
          smooth: true,
          symbol: "circle",
          showSymbol: false,
          symbolSize: 6,
          data: values,
          lineStyle: { width: 2.4, color },
          itemStyle: { color },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: withAlpha(color, 0.38) },
                { offset: 1, color: withAlpha(color, 0) },
              ],
            },
          },
        },
      ],
    };
  }, [c, color, data, key, seriesLabel]);

  return (
    <div className="chartShell">
      <ReactECharts
        option={option}
        style={{ height, width: "100%" }}
        opts={{ renderer: "canvas" }}
        notMerge
        lazyUpdate
      />
    </div>
  );
}

/** Landing hero charts — gentle live demo (visibility-aware, low CPU). */
const LANDING_DEMO_BASE = [
  { label: "1", total: 38, telegram: 18, youtube: 9 },
  { label: "2", total: 52, telegram: 24, youtube: 12 },
  { label: "3", total: 47, telegram: 22, youtube: 11 },
  { label: "4", total: 71, telegram: 34, youtube: 16 },
  { label: "5", total: 64, telegram: 30, youtube: 15 },
  { label: "6", total: 88, telegram: 41, youtube: 21 },
  { label: "7", total: 79, telegram: 37, youtube: 18 },
  { label: "8", total: 96, telegram: 45, youtube: 24 },
  { label: "9", total: 91, telegram: 42, youtube: 22 },
  { label: "10", total: 112, telegram: 52, youtube: 28 },
  { label: "11", total: 104, telegram: 48, youtube: 26 },
  { label: "12", total: 128, telegram: 58, youtube: 32 },
];

const LANDING_SPARK_BASE = [4, 6, 5, 9, 7, 11, 8, 12, 10, 14, 11, 9];

/**
 * Slow interval tick — only when tab is visible.
 * ~2.8s keeps “live” feel without hammering ECharts/main thread.
 */
function useLandingLiveTick(periodMs = 3200) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    let timer = 0;
    const reduced =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return undefined;

    const loop = () => {
      timer = window.setTimeout(() => {
        if (document.visibilityState === "visible") {
          setTick((t) => (t + 1) % 10_000);
        }
        loop();
      }, periodMs);
    };
    loop();
    return () => window.clearTimeout(timer);
  }, [periodMs]);
  return tick;
}

function liveTrendRows(tick) {
  return LANDING_DEMO_BASE.map((row, i) => {
    const w = Math.sin(tick * 0.75 + i * 0.5) * 4.2;
    const w2 = Math.cos(tick * 0.55 + i * 0.38) * 2.4;
    return {
      label: row.label,
      total: Math.max(18, Math.round(row.total + w)),
      telegram: Math.max(8, Math.round(row.telegram + w2)),
      youtube: Math.max(4, Math.round(row.youtube + w * 0.4)),
    };
  });
}

function cosmosArea(from, mid, to) {
  return {
    type: "linear",
    x: 0,
    y: 0,
    x2: 0,
    y2: 1,
    colorStops: [
      { offset: 0, color: from },
      { offset: 0.5, color: mid },
      { offset: 1, color: to },
    ],
  };
}

function landingShell(className, height, option) {
  return (
    <div className={`chartShell landingPreviewChartShell ${className || ""}`.trim()}>
      <ReactECharts
        option={option}
        style={{ height, width: "100%" }}
        opts={{ renderer: "canvas" }}
        notMerge={false}
        lazyUpdate
      />
    </div>
  );
}

/** Multi-series cosmos wave — live micro-updates. */
export function LandingPreviewChart({ height = 110 }) {
  const c = useChartColors();
  const lng = useUiLanguage();
  const tick = useLandingLiveTick(2800);
  const data = useMemo(() => liveTrendRows(tick), [tick]);

  const option = useMemo(() => {
    const labels = data.map((d) => d.label);
    const yt = softenHarsh(c.youtube, 0.38);
    return {
      animationDuration: 0,
      animationDurationUpdate: 900,
      animationEasingUpdate: "cubicInOut",
      grid: { left: 4, right: 6, top: 10, bottom: 2, containLabel: false },
      tooltip: {
        trigger: "axis",
        backgroundColor: c.tooltipBg,
        borderColor: "transparent",
        textStyle: { color: c.tooltipInk, fontSize: 11 },
        axisPointer: { type: "line", lineStyle: { color: c.total, width: 1, opacity: 0.35 } },
        formatter(params) {
          if (!params?.length) return "";
          const day = params[0].axisValueLabel || params[0].name || "";
          const title = tt("Kun {{day}}", lng, { day });
          const lines = params
            .map(
              (p) =>
                `<div style="display:flex;align-items:center;gap:8px;margin-top:3px">` +
                `<span style="width:8px;height:8px;border-radius:999px;background:${p.color};flex-shrink:0"></span>` +
                `<span style="flex:1;padding-right:12px">${p.seriesName}</span>` +
                `<span style="font-weight:700;font-variant-numeric:tabular-nums">${compact(p.value)}</span>` +
                `</div>`,
            )
            .join("");
          return `<div style="opacity:.7;margin-bottom:2px">${title}</div>${lines}`;
        },
      },
      xAxis: { type: "category", data: labels, boundaryGap: false, show: false },
      yAxis: { type: "value", show: false, scale: true },
      series: [
        {
          name: tt("Jami", lng),
          type: "line",
          smooth: 0.45,
          showSymbol: false,
          data: data.map((d) => d.total),
          z: 3,
          lineStyle: {
            width: 2.7,
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 1,
              y2: 0,
              colorStops: [
                { offset: 0, color: c.total },
                { offset: 0.55, color: c.line },
                { offset: 1, color: c.accent },
              ],
            },
            shadowBlur: 10,
            shadowColor: withAlpha(c.total, 0.45),
          },
          itemStyle: { color: c.total },
          areaStyle: {
            color: cosmosArea(withAlpha(c.total, 0.5), withAlpha(c.line, 0.14), withAlpha(c.total, 0)),
          },
        },
        {
          name: tt("Telegram", lng),
          type: "line",
          smooth: 0.45,
          showSymbol: false,
          data: data.map((d) => d.telegram),
          z: 2,
          lineStyle: {
            width: 1.6,
            color: c.telegram,
            shadowBlur: 6,
            shadowColor: withAlpha(c.telegram, 0.4),
          },
          areaStyle: {
            color: cosmosArea(withAlpha(c.telegram, 0.28), withAlpha(c.telegram, 0.08), withAlpha(c.telegram, 0)),
          },
        },
        {
          name: tt("YouTube", lng),
          type: "line",
          smooth: 0.45,
          showSymbol: false,
          data: data.map((d) => d.youtube),
          z: 1,
          lineStyle: { width: 1.35, color: withAlpha(yt, 0.88) },
          areaStyle: {
            color: cosmosArea(withAlpha(yt, 0.18), withAlpha(yt, 0.06), withAlpha(yt, 0)),
          },
        },
      ],
    };
  }, [c, data, lng]);

  return landingShell("landingChartWave", height, option);
}

/** Live brand score gauge (gentle oscillation). */
export function LandingGaugeChart({
  value = 92,
  max = 100,
  height = 128,
  label,
  tone = "accent",
}) {
  const lng = useUiLanguage();
  const tick = useLandingLiveTick(3200);
  const live = useMemo(() => {
    const base = Number(value) || 92;
    const drift = Math.sin(tick * 0.8) * 2.8 + Math.cos(tick * 0.4) * 1.2;
    return Math.max(84, Math.min(98, Math.round(base + drift)));
  }, [tick, value]);
  const resolvedLabel = label ?? tt("AI score", lng);

  return (
    <div className="chartShell landingPreviewChartShell landingChartGauge">
      <PercentGauge
        value={live}
        max={max}
        height={height}
        tone={tone}
        label={resolvedLabel}
        unit="%"
        showTicks
        showLabels
        compact={height < 110}
      />
    </div>
  );
}

/** Live donut — sentiment mix breathes. */
export function LandingDonutChart({ height = 96 }) {
  const c = useChartColors();
  const lng = useUiLanguage();
  const tick = useLandingLiveTick(3400);

  const option = useMemo(() => {
    const pos = Math.max(50, Math.min(66, Math.round(58 + Math.sin(tick * 0.65) * 3.2)));
    const neg = Math.max(11, Math.min(20, Math.round(15 + Math.cos(tick * 0.5) * 2.2)));
    const neu = Math.max(12, 100 - pos - neg);
    const slices = [
      { name: tt("Ijobiy", lng), value: pos, color: c.positive },
      { name: tt("Neytral", lng), value: neu, color: withAlpha(c.axis, 0.75) },
      { name: tt("Salbiy", lng), value: neg, color: softenHarsh(c.negative, 0.4) },
    ];
    return {
      animationDuration: 0,
      animationDurationUpdate: 850,
      animationEasingUpdate: "cubicInOut",
      tooltip: {
        trigger: "item",
        backgroundColor: c.tooltipBg,
        borderColor: "transparent",
        textStyle: { color: c.tooltipInk, fontSize: 11 },
        formatter: (p) => `${p.name}: <b>${p.value}%</b>`,
      },
      series: [
        {
          type: "pie",
          radius: ["56%", "84%"],
          center: ["50%", "50%"],
          padAngle: 3,
          itemStyle: {
            borderRadius: 6,
            shadowBlur: 10,
            shadowColor: withAlpha(c.total, 0.22),
          },
          label: { show: false },
          labelLine: { show: false },
          data: slices.map((s) => ({
            name: s.name,
            value: s.value,
            itemStyle: {
              color: {
                type: "linear",
                x: 0,
                y: 0,
                x2: 1,
                y2: 1,
                colorStops: [
                  { offset: 0, color: softArcColor(s.color, 0.12) },
                  { offset: 1, color: s.color },
                ],
              },
            },
          })),
        },
      ],
      graphic: [
        {
          type: "text",
          left: "center",
          top: "40%",
          style: {
            text: tt("Kayfiyat", lng),
            fill: c.axis,
            fontSize: 9,
            fontWeight: 650,
            textAlign: "center",
          },
        },
        {
          type: "text",
          left: "center",
          top: "52%",
          style: {
            text: `${pos}%`,
            fill: c.total,
            fontSize: 15,
            fontWeight: 740,
            textAlign: "center",
          },
        },
      ],
    };
  }, [c, lng, tick]);

  return landingShell("landingChartDonut", height, option);
}

/** Live platform bars — heights drift like realtime traffic. */
export function LandingBarsChart({ height = 96 }) {
  const c = useChartColors();
  const lng = useUiLanguage();
  const tick = useLandingLiveTick(2900);

  const option = useMemo(() => {
    const cats = [
      tt("Telegram", lng),
      tt("YouTube", lng),
      tt("Instagram", lng),
      tt("Facebook", lng),
    ];
    const base = [42, 28, 19, 14];
    const vals = base.map((v, i) =>
      Math.max(9, Math.round(v + Math.sin(tick * 0.75 + i * 1.0) * (3.5 + i * 0.4))),
    );
    const colors = [
      c.telegram,
      softenHarsh(c.youtube, 0.4),
      softenHarsh(c.instagram, 0.32),
      c.facebook,
    ];
    return {
      animationDuration: 0,
      animationDurationUpdate: 800,
      animationEasingUpdate: "cubicInOut",
      grid: { left: 4, right: 4, top: 10, bottom: 22, containLabel: false },
      tooltip: {
        trigger: "axis",
        backgroundColor: c.tooltipBg,
        borderColor: "transparent",
        textStyle: { color: c.tooltipInk, fontSize: 11 },
        axisPointer: { type: "shadow", shadowStyle: { color: withAlpha(c.total, 0.08) } },
      },
      xAxis: {
        type: "category",
        data: cats,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: c.axis,
          fontSize: 8,
          fontWeight: 650,
          margin: 6,
          interval: 0,
          formatter: (value) => {
            // Compact axis labels so full localized names fit.
            if (value.length <= 3) return value;
            if (value.toLowerCase().startsWith("tele")) return "TG";
            if (value.toLowerCase().startsWith("you")) return "YT";
            if (value.toLowerCase().startsWith("inst")) return "IG";
            if (value.toLowerCase().startsWith("face") || value.toLowerCase().startsWith("фейс")) return "FB";
            return value.slice(0, 2).toUpperCase();
          },
        },
      },
      yAxis: { type: "value", show: false, max: 60 },
      series: [
        {
          name: tt("Platformalar", lng),
          type: "bar",
          data: vals.map((v, i) => ({
            value: v,
            name: cats[i],
            itemStyle: {
              color: {
                type: "linear",
                x: 0,
                y: 0,
                x2: 0,
                y2: 1,
                colorStops: [
                  { offset: 0, color: softArcColor(colors[i], 0.18) },
                  { offset: 0.55, color: colors[i] },
                  { offset: 1, color: withAlpha(colors[i], 0.35) },
                ],
              },
              borderRadius: [7, 7, 3, 3],
              shadowBlur: 8,
              shadowColor: withAlpha(colors[i], 0.35),
            },
          })),
          barWidth: 14,
          showBackground: true,
          backgroundStyle: {
            color: withAlpha(c.axis, 0.1),
            borderRadius: [7, 7, 3, 3],
          },
        },
      ],
    };
  }, [c, lng, tick]);

  return landingShell("landingChartBars", height, option);
}

/** Tiny risk sparkline — scrolling live feel. */
export function LandingSparkChart({ height = 48 }) {
  const c = useChartColors();
  const tick = useLandingLiveTick(2600);
  const riskColor = softenHarsh(c.negative, 0.42);

  const values = useMemo(
    () =>
      LANDING_SPARK_BASE.map((v, i) =>
        Math.max(2, Math.round(v + Math.sin(tick * 0.85 + i * 0.65) * 2)),
      ),
    [tick],
  );

  const option = useMemo(
    () => ({
      animationDuration: 0,
      animationDurationUpdate: 700,
      animationEasingUpdate: "cubicInOut",
      grid: { left: 2, right: 2, top: 6, bottom: 2, containLabel: false },
      xAxis: { type: "category", show: false, data: values.map((_, i) => i) },
      yAxis: { type: "value", show: false, scale: true },
      series: [
        {
          type: "line",
          smooth: true,
          showSymbol: false,
          data: values,
          lineStyle: {
            width: 2,
            color: riskColor,
            shadowBlur: 8,
            shadowColor: withAlpha(riskColor, 0.45),
          },
          areaStyle: {
            color: cosmosArea(withAlpha(riskColor, 0.34), withAlpha(riskColor, 0.1), withAlpha(riskColor, 0)),
          },
        },
      ],
    }),
    [riskColor, values],
  );

  return landingShell("landingChartSpark", height, option);
}

/** Live KPI numbers for hero preview strip. */
export function useLandingLiveKpis() {
  const tick = useLandingLiveTick(3000);
  return useMemo(() => {
    const mentions = 1284 + Math.round(Math.sin(tick * 0.7) * 14 + Math.cos(tick * 0.3) * 6);
    const coverage = Math.max(88, Math.min(96, Math.round(92 + Math.sin(tick * 0.6) * 2)));
    const risk = Math.max(5, Math.min(10, Math.round(7 + Math.sin(tick * 0.9) * 1.5)));
    const trendPct = Math.max(12, Math.min(24, Math.round(18 + Math.sin(tick * 0.45) * 2.5)));
    return { mentions, coverage, risk, trendPct };
  }, [tick]);
}

/** Parse #rgb / #rrggbb / rgb() / rgba() / named → rgba(r,g,b,a) for gradients. */
function withAlpha(color, alpha) {
  if (!color) return `rgba(124,131,255,${alpha})`;
  const c = color.trim();
  if (c.startsWith("rgba(")) {
    return c.replace(/rgba\(([^)]+),\s*[\d.]+\s*\)/, `rgba($1, ${alpha})`);
  }
  if (c.startsWith("rgb(")) {
    return c.replace("rgb(", "rgba(").replace(")", `, ${alpha})`);
  }
  if (c.startsWith("#")) {
    let hex = c.slice(1);
    if (hex.length === 3) {
      hex = hex
        .split("")
        .map((ch) => ch + ch)
        .join("");
    }
    if (hex.length >= 6) {
      const r = parseInt(hex.slice(0, 2), 16);
      const g = parseInt(hex.slice(2, 4), 16);
      const b = parseInt(hex.slice(4, 6), 16);
      return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }
  }
  return c;
}

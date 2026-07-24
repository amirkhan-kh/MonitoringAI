/**
 * Recharts trend charts — replaces the hand-rolled SVG line charts.
 *
 * Colors are read from the CSS design tokens via getComputedStyle and passed to
 * Recharts as REAL values (SVG presentation attributes do NOT support var()),
 * re-read whenever the theme flips — so charts follow dark/light automatically.
 * Refined single gradient-area "wave" synthesized from reference dashboard #8.
 *
 * Data contract unchanged: rows = [{ label|bucket, total, telegram, youtube,
 * instagram, facebook }]. Presentation only — no data/logic here.
 */
import { useEffect, useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const compact = (value) =>
  new Intl.NumberFormat("uz-UZ", { notation: "compact", maximumFractionDigits: 1 }).format(value || 0);

/** Resolve chart colors from CSS tokens; re-resolve on theme change. */
function useChartColors() {
  const [mode, setMode] = useState(() =>
    (typeof document !== "undefined" && document.documentElement.dataset.theme) || "dark",
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
      grid: read("--chart-grid", "rgba(255,255,255,0.06)"),
      axis: read("--chart-axis", "#6b7280"),
      telegram: read("--telegram", "#2aabee"),
      youtube: read("--youtube", "#ff3040"),
      instagram: read("--instagram", "#e4405f"),
      facebook: read("--facebook", "#1877f2"),
    };
  }, [mode]);
}

function normalize(rows) {
  return (rows || []).map((row) => ({ ...row, label: row.label || row.bucket || "" }));
}

function BreakdownTooltip({ active, payload, label, colors }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload || {};
  const items = [
    { key: "total", name: "Jami", color: colors.line },
    { key: "telegram", name: "Telegram", color: colors.telegram },
    { key: "youtube", name: "YouTube", color: colors.youtube },
    { key: "instagram", name: "Instagram", color: colors.instagram },
    { key: "facebook", name: "Facebook", color: colors.facebook },
  ].filter((item) => item.key === "total" || (row[item.key] ?? 0) > 0);
  return (
    <div className="rechartsTooltip">
      <div className="rtLabel">{label}</div>
      {items.map((item) => (
        <div key={item.key} style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 3 }}>
          <span
            style={{ width: 8, height: 8, borderRadius: 999, background: item.color, flexShrink: 0 }}
            aria-hidden="true"
          />
          <span style={{ flex: 1, paddingRight: 12 }}>{item.name}</span>
          <span className="rtValue">{compact(row[item.key])}</span>
        </div>
      ))}
    </div>
  );
}

function SimpleTooltip({ active, payload, label, name, color }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rechartsTooltip">
      <div className="rtLabel">{label}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 3 }}>
        <span style={{ width: 8, height: 8, borderRadius: 999, background: color, flexShrink: 0 }} aria-hidden="true" />
        <span style={{ flex: 1, paddingRight: 12 }}>{name}</span>
        <span className="rtValue">{compact(payload[0].value)}</span>
      </div>
    </div>
  );
}

/** Main chart: one clean gradient "wave" (total). Breakdown lives in the tooltip. */
export function MentionTrendChart({ rows, height = 268 }) {
  const c = useChartColors();
  const data = normalize(rows);
  return (
    <div className="chartShell chartShell--hero">
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 16, right: 16, bottom: 4, left: -6 }}>
          <defs>
            <linearGradient id="mtAreaTotal" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={c.areaFrom} />
              <stop offset="52%" stopColor={c.areaMid} />
              <stop offset="100%" stopColor={c.areaTo} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} strokeDasharray="4 7" stroke={c.grid} />
          <XAxis
            dataKey="label"
            tickLine={false}
            axisLine={false}
            minTickGap={26}
            tickMargin={12}
            tick={{ fill: c.axis, fontSize: 11 }}
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            width={42}
            tickFormatter={compact}
            tick={{ fill: c.axis, fontSize: 11 }}
          />
          <Tooltip
            content={<BreakdownTooltip colors={c} />}
            cursor={{ stroke: c.line, strokeOpacity: 0.35, strokeWidth: 1 }}
          />
          <Area
            type="monotone"
            dataKey="total"
            name="Jami"
            stroke={c.line}
            strokeWidth={2.8}
            fill="url(#mtAreaTotal)"
            dot={false}
            activeDot={{ r: 5, strokeWidth: 0, fill: c.line }}
            isAnimationActive
            animationDuration={750}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Compact single-platform sparkline-style gradient area. */
export function PlatformTrendChart({ rows, series, height = 132 }) {
  const c = useChartColors();
  const data = normalize(rows);
  const color = c[series?.tone] || c.line;
  const gradId = `ptArea-${series?.key || "x"}`;
  return (
    <div className="chartShell">
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 10, right: 6, bottom: 0, left: 6 }}>
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.38} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} strokeDasharray="4 7" stroke={c.grid} />
          <XAxis dataKey="label" hide />
          <YAxis hide domain={[0, "dataMax"]} />
          <Tooltip
            content={<SimpleTooltip name={series?.label} color={color} />}
            cursor={{ stroke: color, strokeOpacity: 0.35, strokeWidth: 1 }}
          />
          <Area
            type="monotone"
            dataKey={series?.key}
            name={series?.label}
            stroke={color}
            strokeWidth={2.4}
            fill={`url(#${gradId})`}
            dot={false}
            activeDot={{ r: 3.5, strokeWidth: 0, fill: color }}
            isAnimationActive
            animationDuration={650}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

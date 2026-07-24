/**
 * Recharts trend charts — replaces the hand-rolled SVG line charts.
 * Colors come from CSS custom properties, so charts follow the dark/light theme
 * automatically (see aesthetic layer v2 in styles.css). Refined gradient-area
 * look synthesized from the reference dashboards (esp. the #8 wave chart).
 *
 * Data contract is unchanged: rows = [{ label|bucket, total, telegram, youtube,
 * instagram, facebook }]. No data/logic lives here — presentation only.
 */
import {
  Area,
  AreaChart,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const compact = (value) =>
  new Intl.NumberFormat("uz-UZ", { notation: "compact", maximumFractionDigits: 1 }).format(value || 0);

const PLATFORM_COLOR = {
  total: "var(--chart-line)",
  telegram: "var(--telegram)",
  youtube: "var(--youtube)",
  instagram: "var(--instagram)",
  facebook: "var(--facebook)",
};

function normalize(rows) {
  return (rows || []).map((row) => ({ ...row, label: row.label || row.bucket || "" }));
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const rows = payload.filter((item) => item.dataKey === "total" || (item.value ?? 0) > 0);
  if (!rows.length) return null;
  return (
    <div className="rechartsTooltip">
      <div className="rtLabel">{label}</div>
      {rows.map((item) => (
        <div key={item.dataKey} style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 3 }}>
          <span
            style={{ width: 8, height: 8, borderRadius: 999, background: item.color, flexShrink: 0 }}
            aria-hidden="true"
          />
          <span style={{ flex: 1, paddingRight: 10 }}>{item.name}</span>
          <span className="rtValue">{compact(item.value)}</span>
        </div>
      ))}
    </div>
  );
}

/** Main mention-trend chart: total as a gradient area, platforms as thin lines. */
export function MentionTrendChart({ rows, height = 264 }) {
  const data = normalize(rows);
  return (
    <div className="chartShell">
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={data} margin={{ top: 14, right: 14, bottom: 4, left: -6 }}>
          <defs>
            <linearGradient id="mtAreaTotal" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--chart-area-from)" />
              <stop offset="55%" stopColor="var(--chart-area-mid)" />
              <stop offset="100%" stopColor="var(--chart-area-to)" />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} strokeDasharray="4 6" />
          <XAxis dataKey="label" tickLine={false} axisLine={false} minTickGap={26} tickMargin={10} />
          <YAxis tickLine={false} axisLine={false} width={42} tickFormatter={compact} />
          <Tooltip
            content={<ChartTooltip />}
            cursor={{ stroke: "var(--chart-line)", strokeOpacity: 0.3, strokeWidth: 1 }}
          />
          <Area
            type="monotone"
            dataKey="total"
            name="Jami"
            stroke="var(--chart-line)"
            strokeWidth={2.6}
            fill="url(#mtAreaTotal)"
            dot={false}
            activeDot={{ r: 4, strokeWidth: 0 }}
            isAnimationActive
            animationDuration={700}
          />
          <Line type="monotone" dataKey="telegram" name="Telegram" stroke="var(--telegram)" strokeWidth={1.5} dot={false} />
          <Line type="monotone" dataKey="youtube" name="YouTube" stroke="var(--youtube)" strokeWidth={1.5} dot={false} />
          <Line type="monotone" dataKey="instagram" name="Instagram" stroke="var(--instagram)" strokeWidth={1.5} dot={false} />
          <Line type="monotone" dataKey="facebook" name="Facebook" stroke="var(--facebook)" strokeWidth={1.5} dot={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Compact single-platform sparkline-style gradient area. */
export function PlatformTrendChart({ rows, series, height = 132 }) {
  const data = normalize(rows);
  const color = PLATFORM_COLOR[series?.tone] || "var(--chart-line)";
  const gradId = `ptArea-${series?.key || "x"}`;
  return (
    <div className="chartShell">
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 10, right: 6, bottom: 0, left: 6 }}>
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.34} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} strokeDasharray="4 6" />
          <XAxis dataKey="label" hide />
          <YAxis hide domain={[0, "dataMax"]} />
          <Tooltip content={<ChartTooltip />} cursor={{ stroke: color, strokeOpacity: 0.3, strokeWidth: 1 }} />
          <Area
            type="monotone"
            dataKey={series?.key}
            name={series?.label}
            stroke={color}
            strokeWidth={2.2}
            fill={`url(#${gradId})`}
            dot={false}
            activeDot={{ r: 3, strokeWidth: 0 }}
            isAnimationActive
            animationDuration={650}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

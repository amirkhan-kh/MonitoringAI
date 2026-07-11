import { Activity, BarChart3, Brain, ShieldAlert } from "lucide-react";

export function StatsBar({ sources = [], summary, items: providedItems, loading = false }) {
  const riskCounts = summary?.risk_counts || {};
  const highRisk = (riskCounts.high || 0) + (riskCounts.critical || 0);
  const items = providedItems || [
    { label: "Source", value: sources.length, icon: Activity },
    { label: "Mention", value: summary?.mentions_total || 0, icon: BarChart3 },
    { label: "AI tahlil", value: summary?.analyzed_total || 0, icon: Brain },
    { label: "High risk", value: highRisk, icon: ShieldAlert },
  ];

  return (
    <section className={loading ? "statsGrid isLoading" : "statsGrid"} aria-busy={loading}>
      {loading &&
        Array.from({ length: 4 }).map((_, index) => (
          <article className="statCard skeletonCard" key={`stat-skeleton-${index}`}>
            <div>
              <span className="skeletonText sm" />
              <span className="skeletonText value" />
            </div>
            <span className="skeletonIcon" />
          </article>
        ))}
      {!loading && items.map((item) => {
        const Icon = item.icon;
        return (
          <article className={`statCard ${item.tone || ""}`} key={item.label}>
            <div>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
            <Icon size={22} />
          </article>
        );
      })}
    </section>
  );
}

import { RefreshCw } from "lucide-react";

export function PageHeader({
  brands,
  selectedBrandId,
  onBrandChange,
  onRefresh,
  eyebrow = "Brand source catalog",
  title = "Telegram monitoring",
  loading = false,
}) {
  return (
    <header className={loading ? "pageHeader isLoading" : "pageHeader"} aria-busy={loading}>
      <div>
        {loading ? (
          <>
            <span className="skeletonText eyebrowSkeleton" />
            <span className="skeletonText titleSkeleton" />
          </>
        ) : (
          <>
            <p className="eyebrow">{eyebrow}</p>
            <h1>{title}</h1>
          </>
        )}
      </div>
      <div className="headerActions">
        {loading ? (
          <>
            <span className="skeletonControl" />
            <span className="skeletonButton" />
          </>
        ) : (
          <>
            <select className="input select" value={selectedBrandId} onChange={(event) => onBrandChange(event.target.value)}>
              <option value="">Barcha brandlar</option>
              {brands.map((brand) => (
                <option key={brand.id} value={brand.id}>
                  {brand.name}
                </option>
              ))}
            </select>
            <button className="button secondary" type="button" onClick={onRefresh}>
              <RefreshCw size={17} />
              <span>Yangilash</span>
            </button>
          </>
        )}
      </div>
    </header>
  );
}

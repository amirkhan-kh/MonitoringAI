import { useTranslation } from "react-i18next";

export function PageHeader({
  eyebrow = "Brand source catalog",
  title = "Telegram monitoring",
  loading = false,
}) {
  const { t } = useTranslation();
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
            <p className="eyebrow">{t(eyebrow, { defaultValue: eyebrow })}</p>
            <h1>{t(title, { defaultValue: title })}</h1>
          </>
        )}
      </div>
    </header>
  );
}

import { useCallback, useEffect, useMemo, useState } from "react";
import { Building2, RefreshCw, Shield, Zap } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  isSuperAdmin,
  superAdminActivateOrg,
  superAdminExtendTrial,
  superAdminListOrgs,
  superAdminSuspendOrg,
} from "../api/client";
import { PageHeader } from "../components/PageHeader";
import { Sidebar } from "../components/Sidebar";
import { SmartSelect } from "../components/SmartSelect";
import { formatUiDate } from "../i18n";
import { navigateTo } from "../navigation";

const PLAN_CODES = [
  { value: "start", label: "Start" },
  { value: "growth", label: "Growth" },
  { value: "business", label: "Business" },
  { value: "scale", label: "Scale" },
];

function statusTone(status) {
  const s = String(status || "").toLowerCase();
  if (s === "active") return "ok";
  if (s === "trial") return "warn";
  if (s === "suspended" || s === "past_due") return "bad";
  return "muted";
}

export function SuperAdmin() {
  const { t, i18n } = useTranslation();
  const locale = { uz: "uz-UZ", ru: "ru-RU", en: "en-US" }[i18n.resolvedLanguage || i18n.language] || "uz-UZ";
  const [orgs, setOrgs] = useState([]);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");
  const [planPick, setPlanPick] = useState({});
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const rows = await superAdminListOrgs();
      setOrgs(Array.isArray(rows) ? rows : []);
    } catch (err) {
      setError(err.message || t("Yuklash xatosi"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    if (!isSuperAdmin()) {
      navigateTo("/umumiy-dashboard", { replace: true });
      return;
    }
    load().catch(() => {});
  }, [load]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return orgs;
    return orgs.filter((org) => {
      const hay = `${org.name || ""} ${org.slug || ""} ${org.status || ""} ${org.plan?.name || ""}`.toLowerCase();
      return hay.includes(q);
    });
  }, [orgs, query]);

  async function activate(orgId) {
    const plan = planPick[orgId] || "growth";
    setBusyId(orgId);
    try {
      await superAdminActivateOrg(orgId, plan, 30);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId("");
    }
  }

  async function extendTrial(orgId) {
    setBusyId(orgId);
    try {
      await superAdminExtendTrial(orgId, 7);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId("");
    }
  }

  async function suspend(orgId) {
    if (!window.confirm(t("Ushbu tashkilot suspended qilinsinmi?"))) return;
    setBusyId(orgId);
    try {
      await superAdminSuspendOrg(orgId);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId("");
    }
  }

  const trialCount = orgs.filter((o) => o.status === "trial").length;
  const activeCount = orgs.filter((o) => o.status === "active").length;

  return (
    <div className="appShell">
      <Sidebar activePath="/super-admin" />
      <main className="main">
        <PageHeader
          eyebrow="Platform control"
          title="Super Admin"
          loading={loading}
        />
        <p className="sectionLead">
          {t("Tashkilotlar, trial va manual tarif yoqish. To‘lov tashqi (UZS/USD); shu yerdan plan faollashtiriladi.")}
        </p>

        {error ? <div className="errorBanner">{error}</div> : null}

        <section className="panel superAdminToolbar">
          <label className="field superAdminSearch">
            <span>{t("Qidiruv")}</span>
            <input
              className="input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("Tashkilot, slug yoki status...")}
            />
          </label>
          <button className="button" type="button" onClick={() => load()} disabled={loading}>
            <RefreshCw size={16} />
            <span>{t("Yangilash")}</span>
          </button>
          <div className="superAdminStats">
            <span className="statChip">
              <Building2 size={14} /> {orgs.length} {t("tashkilot")}
            </span>
            <span className="statChip">
              <Zap size={14} /> {trialCount} {t("trial")}
            </span>
            <span className="statChip ok">
              <Shield size={14} /> {activeCount} {t("active")}
            </span>
          </div>
        </section>

        <section className="panel superAdminTablePanel">
          <div className="superAdminTableWrap">
            <table className="superAdminTable">
              <thead>
                <tr>
                  <th>{t("Tashkilot")}</th>
                  <th>{t("Status")}</th>
                  <th>{t("Plan")}</th>
                  <th>{t("AI usage")}</th>
                  <th>{t("Trial tugashi")}</th>
                  <th>{t("Amallar")}</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((org) => (
                  <tr key={org.id}>
                    <td>
                      <strong className="superAdminOrgName">{org.name}</strong>
                      <div className="muted small">{org.slug}</div>
                    </td>
                    <td>
                      <em className={`state ${statusTone(org.status)}`}>{t(org.status || "—", { defaultValue: org.status || "—" })}</em>
                    </td>
                    <td>
                      <strong>{org.plan?.name || "—"}</strong>
                      {org.plan ? (
                        <div className="muted small">
                          ${org.plan.price_usd} · {(org.plan.price_uzs || 0).toLocaleString(locale)} {t("so‘m")}
                        </div>
                      ) : null}
                    </td>
                    <td>
                      <span className="superAdminUsage">
                        {org.usage?.ai_analyses ?? 0}
                        <span className="muted"> / {org.usage?.ai_limit ?? "—"}</span>
                      </span>
                    </td>
                    <td className="small">
                      {org.trial_ends_at
                        ? formatUiDate(org.trial_ends_at, { dateStyle: "medium", timeStyle: "short" })
                        : "—"}
                    </td>
                    <td>
                      <div className="superAdminActions">
                        <div className="superAdminPlanSelect">
                          <SmartSelect
                            value={planPick[org.id] || "growth"}
                            options={PLAN_CODES}
                            onChange={(value) => setPlanPick((p) => ({ ...p, [org.id]: value }))}
                            ariaLabel={t("Plan tanlash")}
                          />
                        </div>
                        <button
                          type="button"
                          className="button primary"
                          disabled={busyId === org.id}
                          onClick={() => activate(org.id)}
                        >
                          {t("To‘lovni yoqish")}
                        </button>
                        <button
                          type="button"
                          className="button secondary"
                          disabled={busyId === org.id}
                          onClick={() => extendTrial(org.id)}
                        >
                          {t("+7 kun trial")}
                        </button>
                        <button
                          type="button"
                          className="button"
                          disabled={busyId === org.id}
                          onClick={() => suspend(org.id)}
                        >
                          {t("Suspend")}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {!filtered.length ? (
                  <tr>
                    <td colSpan={6} className="muted superAdminEmpty">
                      {loading ? t("Yuklanmoqda...") : t("Mos tashkilot topilmadi.")}
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  );
}

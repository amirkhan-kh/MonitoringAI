"""Plans, trial, usage metering for multi-tenant SaaS."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import Brand, Organization, Plan, Subscription, UsageMonthly, utcnow

TRIAL_DAYS = 7
TRIAL_AI_LIMIT = 100

DEFAULT_PLANS: list[dict[str, Any]] = [
    {
        "code": "trial",
        "name": "Trial",
        "price_usd": 0,
        "price_uzs": 0,
        "ai_mention_limit_monthly": TRIAL_AI_LIMIT,
        "brands_limit": 1,
        "seats_limit": 1,
        "platforms": ["telegram", "instagram", "youtube"],
        "features": {"ai_tier": "flash", "alerts": True},
        "sort_order": 0,
    },
    {
        "code": "start",
        "name": "Start",
        "price_usd": 49,
        "price_uzs": 599_000,
        "ai_mention_limit_monthly": 2000,
        "brands_limit": 1,
        "seats_limit": 1,
        "platforms": ["telegram", "instagram"],
        "features": {"ai_tier": "flash", "alerts": False, "support": "email"},
        "sort_order": 10,
    },
    {
        "code": "growth",
        "name": "Growth",
        "price_usd": 99,
        "price_uzs": 1_199_000,
        "ai_mention_limit_monthly": 8000,
        "brands_limit": 2,
        "seats_limit": 3,
        "platforms": ["telegram", "instagram", "youtube"],
        "features": {"ai_tier": "hybrid", "alerts": True, "support": "priority"},
        "sort_order": 20,
    },
    {
        "code": "business",
        "name": "Business",
        "price_usd": 249,
        "price_uzs": 2_999_000,
        "ai_mention_limit_monthly": 25000,
        "brands_limit": 5,
        "seats_limit": 10,
        "platforms": ["telegram", "instagram", "youtube", "facebook"],
        "features": {"ai_tier": "pro", "alerts": True, "export": True, "support": "sla"},
        "sort_order": 30,
    },
    {
        "code": "scale",
        "name": "Scale",
        "price_usd": 599,
        "price_uzs": 7_199_000,
        "ai_mention_limit_monthly": 80000,
        "brands_limit": 20,
        "seats_limit": 25,
        "platforms": ["telegram", "instagram", "youtube", "facebook"],
        "features": {"ai_tier": "pro", "alerts": True, "export": True, "api": True, "support": "dedicated"},
        "sort_order": 40,
    },
]


def slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (name or "org").lower()).strip("-") or "org"
    return base[:60]


def unique_slug(session: Session, name: str) -> str:
    base = slugify(name)
    candidate = base
    n = 0
    while session.query(Organization.id).filter(Organization.slug == candidate).first():
        n += 1
        candidate = f"{base}-{n}"
    return candidate


def current_year_month(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return now.strftime("%Y-%m")


def ensure_default_plans(session: Session) -> dict[str, Plan]:
    by_code: dict[str, Plan] = {}
    for spec in DEFAULT_PLANS:
        plan = session.query(Plan).filter(Plan.code == spec["code"]).one_or_none()
        if plan is None:
            plan = Plan(**spec)
            session.add(plan)
            session.flush()
        else:
            for key, value in spec.items():
                setattr(plan, key, value)
        by_code[plan.code] = plan
    return by_code


def get_plan(session: Session, plan_id: uuid.UUID | None) -> Plan | None:
    if not plan_id:
        return None
    return session.get(Plan, plan_id)


def org_is_access_allowed(org: Organization | None) -> bool:
    if org is None:
        return False
    if org.status == "suspended":
        return False
    if org.status == "trial" and org.trial_ends_at:
        end = org.trial_ends_at
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        if end < datetime.now(timezone.utc):
            return False
    return org.status in {"trial", "active"}


def effective_ai_limit(org: Organization, plan: Plan | None) -> int:
    if org.status == "trial":
        return int(org.trial_ai_mention_limit or TRIAL_AI_LIMIT)
    if plan:
        return int(plan.ai_mention_limit_monthly or 0)
    return TRIAL_AI_LIMIT


def effective_brands_limit(org: Organization, plan: Plan | None) -> int:
    if org.status == "trial":
        return 1
    if plan:
        return int(plan.brands_limit or 1)
    return 1


def get_or_create_usage(session: Session, org_id: uuid.UUID, year_month: str | None = None) -> UsageMonthly:
    ym = year_month or current_year_month()
    row = (
        session.query(UsageMonthly)
        .filter(UsageMonthly.organization_id == org_id, UsageMonthly.year_month == ym)
        .one_or_none()
    )
    if row is None:
        row = UsageMonthly(organization_id=org_id, year_month=ym)
        session.add(row)
        session.flush()
    return row


def increment_ai_usage(session: Session, org_id: uuid.UUID | None, count: int = 1) -> UsageMonthly | None:
    if not org_id:
        return None
    row = get_or_create_usage(session, org_id)
    row.ai_analyses = int(row.ai_analyses or 0) + count
    row.updated_at = utcnow()
    session.add(row)
    return row


def org_ai_usage_count(session: Session, org_id: uuid.UUID) -> int:
    row = get_or_create_usage(session, org_id)
    return int(row.ai_analyses or 0)


def org_can_analyze(session: Session, org: Organization | None) -> tuple[bool, str]:
    if org is None:
        return False, "organization_missing"
    if not org_is_access_allowed(org):
        return False, "org_inactive_or_trial_expired"
    plan = get_plan(session, org.plan_id)
    limit = effective_ai_limit(org, plan)
    used = org_ai_usage_count(session, org.id)
    if used >= limit:
        return False, "ai_quota_exceeded"
    return True, "ok"


def plan_summary(plan: Plan | None) -> dict[str, Any] | None:
    if not plan:
        return None
    return {
        "id": str(plan.id),
        "code": plan.code,
        "name": plan.name,
        "price_usd": plan.price_usd,
        "price_uzs": plan.price_uzs,
        "ai_mention_limit_monthly": plan.ai_mention_limit_monthly,
        "brands_limit": plan.brands_limit,
        "seats_limit": plan.seats_limit,
        "platforms": plan.platforms or [],
        "features": plan.features or {},
    }


def usage_summary(session: Session, org: Organization | None) -> dict[str, Any] | None:
    if org is None:
        return None
    plan = get_plan(session, org.plan_id)
    limit = effective_ai_limit(org, plan)
    used = org_ai_usage_count(session, org.id)
    brands_used = session.query(Brand).filter(Brand.organization_id == org.id).count()
    brands_limit = effective_brands_limit(org, plan)
    return {
        "year_month": current_year_month(),
        "ai_analyses": used,
        "ai_limit": limit,
        "ai_remaining": max(0, limit - used),
        "brands_used": brands_used,
        "brands_limit": brands_limit,
        "trial_ends_at": org.trial_ends_at.isoformat() if org.trial_ends_at else None,
        "org_status": org.status,
    }


def create_trial_org(
    session: Session,
    *,
    name: str,
    owner_user_id: uuid.UUID,
    preferred_plan_code: str | None = None,
) -> Organization:
    plans = ensure_default_plans(session)
    trial_plan = plans.get("trial") or plans.get("start")
    # preferred_plan is remembered for upgrade UX; trial still uses trial limits
    org = Organization(
        name=name.strip() or "My workspace",
        slug=unique_slug(session, name),
        owner_user_id=owner_user_id,
        status="trial",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=TRIAL_DAYS),
        trial_ai_mention_limit=TRIAL_AI_LIMIT,
        plan_id=trial_plan.id if trial_plan else None,
    )
    session.add(org)
    session.flush()
    sub = Subscription(
        organization_id=org.id,
        plan_id=trial_plan.id if trial_plan else plans["start"].id,
        status="trial",
        current_period_start=datetime.now(timezone.utc),
        current_period_end=org.trial_ends_at,
        payment_provider="manual",
    )
    session.add(sub)
    # Store preferred paid plan code in notes for super-admin
    if preferred_plan_code and preferred_plan_code not in {"trial", ""}:
        org.notes = f"preferred_plan={preferred_plan_code}"
    return org


def activate_org_plan(
    session: Session,
    org: Organization,
    plan: Plan,
    *,
    activated_by: uuid.UUID | None = None,
    period_days: int = 30,
) -> Subscription:
    now = datetime.now(timezone.utc)
    org.status = "active"
    org.plan_id = plan.id
    org.trial_ends_at = None
    session.add(org)
    sub = Subscription(
        organization_id=org.id,
        plan_id=plan.id,
        status="active",
        current_period_start=now,
        current_period_end=now + timedelta(days=period_days),
        payment_provider="manual",
        activated_by_user_id=activated_by,
    )
    session.add(sub)
    session.flush()
    return sub

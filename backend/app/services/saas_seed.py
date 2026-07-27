"""Bootstrap plans, internal org, and attach legacy brands on startup."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.entities import Brand, Organization, OrganizationMember, User
from app.services.auth import hash_password, normalize_email
from app.services.billing import ensure_default_plans, unique_slug

logger = logging.getLogger("saas-seed")


def seed_saas(session: Session) -> None:
    settings = get_settings()
    plans = ensure_default_plans(session)

    # Super admin from env
    admin_login = (settings.admin_username or "admin").strip()
    admin_email = normalize_email(admin_login)
    if "@" not in admin_email:
        admin_email = f"{admin_email}@local.monitoringai"
    password = settings.admin_password or "changeme"
    admin = session.query(User).filter(User.email == admin_email).one_or_none()
    if admin is None:
        admin = User(
            email=admin_email,
            password_hash=hash_password(password),
            full_name="Super Admin",
            is_super_admin=True,
            status="active",
        )
        session.add(admin)
        session.flush()
        logger.info("Created super_admin user %s", admin_email)
    else:
        admin.is_super_admin = True
        if settings.admin_password:
            admin.password_hash = hash_password(settings.admin_password)
        session.add(admin)

    # Internal org for existing brands
    internal = session.query(Organization).filter(Organization.slug == "aviora-internal").one_or_none()
    if internal is None:
        trial_plan = plans.get("business") or plans.get("growth") or plans.get("trial")
        internal = Organization(
            name="Aviora Internal",
            slug="aviora-internal",
            owner_user_id=admin.id,
            status="active",
            plan_id=trial_plan.id if trial_plan else None,
            trial_ai_mention_limit=100000,
            notes="Migrated legacy single-tenant workspace",
        )
        session.add(internal)
        session.flush()
        logger.info("Created Aviora Internal organization")

    member = (
        session.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == internal.id,
            OrganizationMember.user_id == admin.id,
        )
        .one_or_none()
    )
    if member is None:
        session.add(
            OrganizationMember(organization_id=internal.id, user_id=admin.id, role="owner")
        )

    # Attach orphan brands
    orphans = session.query(Brand).filter(Brand.organization_id.is_(None)).all()
    for brand in orphans:
        brand.organization_id = internal.id
        session.add(brand)
    if orphans:
        logger.info("Attached %s legacy brands to Aviora Internal", len(orphans))

    session.commit()

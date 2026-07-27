"""Organization / brand ACL helpers."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy.orm import Query, Session

from app.config import get_settings
from app.models.entities import Brand, Organization
from app.services.auth import AuthContext, decode_token


def auth_from_request(request: Request) -> AuthContext | None:
    settings = get_settings()
    if not settings.auth_enabled:
        return AuthContext(
            user_id=None,
            email="dev",
            org_id=None,
            role="super_admin",
            is_super_admin=True,
            username="dev",
        )
    header = request.headers.get("Authorization", "")
    token = header[7:] if header.startswith("Bearer ") else None
    return decode_token(settings, token)


def require_auth_context(request: Request) -> AuthContext:
    ctx = auth_from_request(request)
    if ctx is None:
        raise HTTPException(status_code=401, detail="Avtorizatsiya talab qilinadi. Qaytadan kiring.")
    return ctx


def get_org(session: Session, org_id: uuid.UUID | None) -> Organization | None:
    if not org_id:
        return None
    return session.get(Organization, org_id)


def assert_brand_access(session: Session, ctx: AuthContext, brand: Brand | None) -> Brand:
    if brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    if ctx.is_super_admin:
        return brand
    # Regular users only see brands they personally created (not other clients' workspaces).
    if ctx.user_id is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    if brand.created_by_user_id is not None and brand.created_by_user_id != ctx.user_id:
        raise HTTPException(status_code=404, detail="Brand not found")
    # Legacy rows without creator: fall back to organization membership.
    if brand.created_by_user_id is None:
        if ctx.org_id is None or brand.organization_id is None or brand.organization_id != ctx.org_id:
            raise HTTPException(status_code=404, detail="Brand not found")
    return brand


def load_brand_for_user(session: Session, ctx: AuthContext, brand_id: uuid.UUID) -> Brand:
    brand = session.get(Brand, brand_id)
    return assert_brand_access(session, ctx, brand)


def brands_query_for_user(session: Session, ctx: AuthContext):
    q = session.query(Brand)
    if ctx.is_super_admin:
        return q
    if ctx.user_id is None:
        return q.filter(False)
    # Prefer creator ownership; include legacy org-scoped brands still missing creator.
    if ctx.org_id is not None:
        return q.filter(
            (Brand.created_by_user_id == ctx.user_id)
            | (
                (Brand.created_by_user_id.is_(None))
                & (Brand.organization_id == ctx.org_id)
            )
        )
    return q.filter(Brand.created_by_user_id == ctx.user_id)


def accessible_brand_ids(session: Session, ctx: AuthContext) -> list[uuid.UUID] | None:
    """Brand IDs the caller may read.

    - ``None`` → unrestricted (super_admin)
    - ``[]`` → no brands (new tenant / empty workspace)
    - ``[uuid, ...]`` → only these brands
    """
    if ctx.is_super_admin:
        return None
    if ctx.user_id is None:
        return []
    rows = brands_query_for_user(session, ctx).with_entities(Brand.id).all()
    return [row[0] for row in rows]


def resolve_brand_scope(
    session: Session,
    request: Request,
    brand_id: uuid.UUID | None = None,
) -> tuple[AuthContext, list[uuid.UUID] | None, uuid.UUID | None]:
    """Validate optional brand_id and return (ctx, allowed_ids, scoped_brand_id)."""
    ctx = require_auth_context(request)
    allowed = accessible_brand_ids(session, ctx)
    if brand_id is not None:
        load_brand_for_user(session, ctx, brand_id)
        return ctx, allowed, brand_id
    return ctx, allowed, None


def apply_brand_scope(
    query: Any,
    brand_column: Any,
    allowed_ids: list[uuid.UUID] | None,
    brand_id: uuid.UUID | None = None,
) -> Any:
    """Restrict a SQLAlchemy query to the caller's brand scope."""
    if brand_id is not None:
        return query.filter(brand_column == brand_id)
    if allowed_ids is None:
        return query
    if not allowed_ids:
        return query.filter(False)
    return query.filter(brand_column.in_(allowed_ids))


def require_super_admin(ctx: AuthContext) -> None:
    if not ctx.is_super_admin:
        raise HTTPException(status_code=403, detail="Faqat super admin")

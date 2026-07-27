"""Multi-user auth: scrypt password hashes + HMAC signed tokens.

Legacy env admin (ADMIN_USERNAME / ADMIN_PASSWORD) is still accepted and maps to
the bootstrap super_admin user so existing operators are not locked out.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings
from app.models.entities import Organization, OrganizationMember, User


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sign(settings: Settings, body: str) -> str:
    digest = hmac.new(settings.jwt_secret.encode(), body.encode(), hashlib.sha256).digest()
    return _b64e(digest)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${key.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt_hex, key_hex = stored.split("$", 2)
        if algo != "scrypt":
            return False
        salt = bytes.fromhex(salt_hex)
        key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
        return secrets.compare_digest(key.hex(), key_hex)
    except Exception:
        return False


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(normalize_email(email)))


@dataclass
class AuthContext:
    user_id: uuid.UUID | None
    email: str
    org_id: uuid.UUID | None
    role: str  # owner|admin|member|viewer|super_admin
    is_super_admin: bool
    username: str  # display / back-compat

    @property
    def can_write(self) -> bool:
        return self.role in {"owner", "admin", "member", "super_admin"}


def create_token(
    settings: Settings,
    *,
    user_id: uuid.UUID | str | None,
    email: str,
    org_id: uuid.UUID | str | None,
    role: str,
    is_super_admin: bool = False,
) -> tuple[str, int]:
    expires_at = int(time.time()) + settings.jwt_expire_hours * 3600
    payload = {
        "sub": str(user_id) if user_id else email,
        "email": email,
        "org_id": str(org_id) if org_id else None,
        "role": role,
        "is_super_admin": bool(is_super_admin),
        "exp": expires_at,
    }
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode())
    return f"{body}.{_sign(settings, body)}", expires_at


def verify_token(settings: Settings, token: str | None) -> str | None:
    """Back-compat: return email/username string if token valid, else None."""
    ctx = decode_token(settings, token)
    return ctx.email if ctx else None


def decode_token(settings: Settings, token: str | None) -> AuthContext | None:
    if not token or "." not in token:
        return None
    body, _, signature = token.partition(".")
    if not hmac.compare_digest(_sign(settings, body), signature):
        return None
    try:
        payload = json.loads(_b64d(body))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    email = str(payload.get("email") or payload.get("sub") or "")
    if not email:
        return None
    user_id = None
    raw_sub = payload.get("sub")
    if raw_sub:
        try:
            user_id = uuid.UUID(str(raw_sub))
        except ValueError:
            user_id = None
    org_id = None
    raw_org = payload.get("org_id")
    if raw_org:
        try:
            org_id = uuid.UUID(str(raw_org))
        except ValueError:
            org_id = None
    is_super = bool(payload.get("is_super_admin"))
    role = str(payload.get("role") or ("super_admin" if is_super else "member"))
    return AuthContext(
        user_id=user_id,
        email=email,
        org_id=org_id,
        role=role,
        is_super_admin=is_super,
        username=email,
    )


def verify_credentials(settings: Settings, username: str, password: str) -> bool:
    """Legacy env-admin check (constant-time)."""
    if not settings.admin_username or not settings.admin_password:
        return False
    user_ok = hmac.compare_digest(username or "", settings.admin_username)
    pass_ok = hmac.compare_digest(password or "", settings.admin_password)
    return user_ok and pass_ok


def authenticate_user(session: Session, settings: Settings, login: str, password: str) -> User | None:
    """Resolve email/username + password to a User (creates super_admin from env on first env login)."""
    login_norm = (login or "").strip()
    if not login_norm or not password:
        return None

    # 1) DB user by email
    email = normalize_email(login_norm)
    user = session.query(User).filter(User.email == email).one_or_none()
    if user and user.status == "active" and verify_password(password, user.password_hash):
        return user

    # 2) Legacy env admin (username may not be an email)
    if verify_credentials(settings, login_norm, password):
        admin_email = normalize_email(settings.admin_username)
        if "@" not in admin_email:
            admin_email = f"{admin_email}@local.monitoringai"
        user = session.query(User).filter(User.email == admin_email).one_or_none()
        if user is None:
            user = User(
                email=admin_email,
                password_hash=hash_password(password),
                full_name="Super Admin",
                is_super_admin=True,
                status="active",
            )
            session.add(user)
            session.flush()
        else:
            user.is_super_admin = True
            user.password_hash = hash_password(password)
            user.status = "active"
        return user

    return None


def primary_membership(session: Session, user: User) -> OrganizationMember | None:
    return (
        session.query(OrganizationMember)
        .filter(OrganizationMember.user_id == user.id)
        .order_by(OrganizationMember.created_at.asc())
        .first()
    )


def issue_session_token(session: Session, settings: Settings, user: User) -> tuple[str, int, AuthContext]:
    member = primary_membership(session, user)
    org_id = member.organization_id if member else None
    role = "super_admin" if user.is_super_admin else (member.role if member else "member")
    user.last_login_at = datetime.now(timezone.utc)
    session.add(user)
    session.commit()
    token, expires_at = create_token(
        settings,
        user_id=user.id,
        email=user.email,
        org_id=org_id,
        role=role,
        is_super_admin=user.is_super_admin,
    )
    ctx = AuthContext(
        user_id=user.id,
        email=user.email,
        org_id=org_id,
        role=role,
        is_super_admin=user.is_super_admin,
        username=user.email,
    )
    return token, expires_at, ctx


def token_response_dict(
    *,
    token: str,
    expires_at: int,
    user: User,
    ctx: AuthContext,
    org: Organization | None = None,
    plan_summary: dict[str, Any] | None = None,
    usage_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user.email,
        "email": user.email,
        "full_name": user.full_name,
        "user_id": str(user.id),
        "org_id": str(ctx.org_id) if ctx.org_id else None,
        "org_name": org.name if org else None,
        "org_status": org.status if org else None,
        "role": ctx.role,
        "is_super_admin": ctx.is_super_admin,
        "expires_at": expires_at,
        "plan": plan_summary,
        "usage": usage_summary,
    }

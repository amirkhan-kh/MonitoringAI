"""Minimal, dependency-free auth: a compact HMAC-SHA256 signed token (JWT-shaped)
plus constant-time credential checks. No external libraries — the token is
``base64url(payload).base64url(hmac(payload))`` signed with ``settings.jwt_secret``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from app.config import Settings


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sign(settings: Settings, body: str) -> str:
    digest = hmac.new(settings.jwt_secret.encode(), body.encode(), hashlib.sha256).digest()
    return _b64e(digest)


def create_token(settings: Settings, username: str) -> tuple[str, int]:
    """Return (token, expires_at_epoch)."""
    expires_at = int(time.time()) + settings.jwt_expire_hours * 3600
    body = _b64e(json.dumps({"sub": username, "exp": expires_at}, separators=(",", ":")).encode())
    return f"{body}.{_sign(settings, body)}", expires_at


def verify_token(settings: Settings, token: str | None) -> str | None:
    """Return the username if the token is valid and unexpired, else None."""
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
    sub = payload.get("sub")
    return sub if isinstance(sub, str) else None


def verify_credentials(settings: Settings, username: str, password: str) -> bool:
    if not settings.admin_username or not settings.admin_password:
        return False
    # constant-time compare on both fields
    user_ok = hmac.compare_digest(username or "", settings.admin_username)
    pass_ok = hmac.compare_digest(password or "", settings.admin_password)
    return user_ok and pass_ok

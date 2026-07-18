"""Facebook (Meta) Graph API client for Page comment monitoring.

Mirrors instagram_api.py. Comments on a Page's posts arrive as minimal webhook
events (``feed`` field); we fetch the full object via the Graph API with the Page's
access token. Also used by the poller to backfill recent post comments.

Docs: https://developers.facebook.com/docs/graph-api/reference/page/feed
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import httpx


class FacebookApiError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


def _meta_error_code(response: httpx.Response) -> int | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    error = payload.get("error") if isinstance(payload, dict) else None
    raw_code = error.get("code") if isinstance(error, dict) else None
    try:
        return int(raw_code) if raw_code is not None else None
    except (TypeError, ValueError):
        return None


def _http_error(response: httpx.Response, *, operation: str) -> FacebookApiError:
    error_code = _meta_error_code(response)
    message = f"Facebook Graph API {operation} failed (HTTP {response.status_code})"
    if error_code is not None:
        message += f" (Meta code {error_code})"
    return FacebookApiError(message, status_code=response.status_code, error_code=error_code)


# Facebook comment field set (differs from Instagram: ``message`` not ``text``,
# ``created_time`` not ``timestamp``, ``from{name,id}``).
_COMMENT_FIELDS = "id,message,from{id,name},created_time,like_count,comment_count,permalink_url,parent{id}"
_REPLY_FIELDS = "id,message,from{id,name},created_time,like_count,permalink_url,parent{id}"


class FacebookApi:
    def __init__(
        self,
        access_token: str,
        *,
        graph_version: str = "v21.0",
        api_base: str = "graph.facebook.com",
        timeout: float = 20.0,
    ) -> None:
        self.access_token = access_token
        self.base_url = f"https://{api_base}/{graph_version}"
        self._timeout = timeout

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        query = dict(params or {})
        query.pop("access_token", None)
        try:
            response = httpx.get(
                f"{self.base_url}/{path.lstrip('/')}",
                params=query,
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=self._timeout,
            )
        except httpx.HTTPError:
            raise FacebookApiError("Facebook Graph API request failed (network error)") from None
        if response.status_code >= 400:
            raise _http_error(response, operation="request")
        try:
            return response.json()
        except ValueError:
            raise FacebookApiError("Facebook Graph API returned an invalid response") from None

    # --- fetch full objects referenced by a webhook ---
    def get_comment(self, comment_id: str) -> dict[str, Any]:
        return self._get(comment_id, {"fields": _COMMENT_FIELDS})

    # --- poller / backfill helpers ---
    def get_page(self, page_id: str) -> dict[str, Any]:
        return self._get(page_id, {"fields": "id,name,username,fan_count,category"})

    def get_recent_posts(self, page_id: str, limit: int = 25) -> list[dict[str, Any]]:
        fields = "id,message,story,created_time,permalink_url"
        data = self._get(f"{page_id}/posts", {"fields": fields, "limit": limit})
        return data.get("data", []) or []

    def get_post_comments(self, post_id: str, limit: int = 100) -> list[dict[str, Any]]:
        fields = f"{_COMMENT_FIELDS},comments{{{_REPLY_FIELDS}}}"
        data = self._get(
            f"{post_id}/comments",
            {"fields": fields, "limit": limit, "filter": "toplevel", "order": "reverse_chronological"},
        )
        return data.get("data", []) or []


def verify_signature(app_secret: str, raw_body: bytes, header_signature: str | None) -> bool:
    """Validate Meta's X-Hub-Signature-256 header so only Meta can post to the webhook."""
    if not header_signature or not app_secret:
        return False
    prefix = "sha256="
    if not header_signature.startswith(prefix):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header_signature[len(prefix):])


def detect_page(access_token: str, *, graph_version: str = "v21.0") -> dict[str, Any]:
    """Given ONLY an access token, auto-detect the Facebook Page it grants and the
    best token to store. Tries two token shapes:
      1. Facebook User token -> /me/accounts (pick a managed page; store its long-lived
         PAGE token, which is what comment/feed reads actually need).
      2. Facebook Page token -> /me?fields=id,name,category (a page token resolves to
         the page itself).

    Returns {page_id, page_name, username, api_base, access_token} or raises
    FacebookApiError with a human-readable reason for the dashboard.
    """
    errors: list[str] = []
    fb = f"https://graph.facebook.com/{graph_version}"

    def _try(url: str, params: dict) -> dict[str, Any] | None:
        try:
            r = httpx.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=20.0,
            )
        except httpx.HTTPError:
            errors.append("tarmoq xatosi")
            return None
        if r.status_code >= 400:
            error_code = _meta_error_code(r)
            detail = f"HTTP {r.status_code}"
            if error_code is not None:
                detail += f" (Meta code {error_code})"
            errors.append(detail)
            return None
        try:
            return r.json()
        except ValueError:
            errors.append("yaroqsiz API javobi")
            return None

    # 1) User token -> managed pages (with their own page tokens)
    data = _try(
        f"{fb}/me/accounts",
        {"fields": "id,name,username,access_token,category", "limit": 50},
    )
    if data:
        pages = data.get("data", []) or []
        if pages:
            page = pages[0]
            return {
                "page_id": str(page.get("id")),
                "page_name": page.get("name"),
                "username": page.get("username"),
                "api_base": "graph.facebook.com",
                "access_token": page.get("access_token") or access_token,
            }

    # 2) Page token -> the page itself (pages carry a ``category``)
    data = _try(f"{fb}/me", {"fields": "id,name,username,category"})
    if data and data.get("id") and data.get("category"):
        return {
            "page_id": str(data["id"]),
            "page_name": data.get("name"),
            "username": data.get("username"),
            "api_base": "graph.facebook.com",
            "access_token": access_token,
        }

    if not errors:
        errors.append("token'ga hech qanday Facebook Page biriktirilmagan")
    raise FacebookApiError("Token'dan Facebook Page aniqlanmadi. Sabab: " + " | ".join(errors[:3]))

"""Instagram (Meta) Graph API client.

Webhook payloads are intentionally minimal (just IDs), so when a comment/mention
event arrives we call the Graph API with the connected account's access token to
fetch the full text, author, media and permalink. Also used by the poller worker to
backfill recent comments on the account's own media.

Docs: https://developers.facebook.com/docs/instagram-platform
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import httpx


class InstagramApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class InstagramApi:
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
        query = {"access_token": self.access_token, **(params or {})}
        try:
            response = httpx.get(f"{self.base_url}/{path.lstrip('/')}", params=query, timeout=self._timeout)
        except httpx.HTTPError as exc:
            raise InstagramApiError(f"Instagram Graph API request failed: {exc}") from exc
        if response.status_code >= 400:
            raise InstagramApiError(
                f"Instagram Graph API {response.status_code}: {response.text[:300]}",
                status_code=response.status_code,
            )
        return response.json()

    # --- fetch full objects referenced by a webhook ---
    def get_comment(self, comment_id: str) -> dict[str, Any]:
        fields = "id,text,username,timestamp,like_count,media{id,media_type,permalink,caption},parent_id,from"
        return self._get(comment_id, {"fields": fields})

    def get_media(self, media_id: str) -> dict[str, Any]:
        fields = "id,caption,media_type,media_url,permalink,timestamp,username,like_count,comments_count"
        return self._get(media_id, {"fields": fields})

    # --- poller / backfill helpers ---
    def get_account(self, ig_user_id: str) -> dict[str, Any]:
        return self._get(ig_user_id, {"fields": "id,username,name,followers_count,media_count"})

    def get_recent_media(self, ig_user_id: str, limit: int = 25) -> list[dict[str, Any]]:
        # media_url is a long, expiring CDN URL and changes often; permalink is stable
        # and sufficient for the monitoring UI, so polling avoids needless DB churn.
        fields = "id,caption,media_type,permalink,timestamp,username,like_count,comments_count"
        remaining = max(1, limit)
        cursor: str | None = None
        items: list[dict[str, Any]] = []
        while remaining > 0:
            params: dict[str, Any] = {"fields": fields, "limit": min(100, remaining)}
            if cursor:
                params["after"] = cursor
            payload = self._get(f"{ig_user_id}/media", params)
            page = payload.get("data", []) or []
            items.extend(page)
            remaining -= len(page)
            next_cursor = ((payload.get("paging") or {}).get("cursors") or {}).get("after")
            if not page or remaining <= 0 or not next_cursor:
                break
            cursor = str(next_cursor)
        return items[:limit]

    def get_media_comments(self, media_id: str, limit: int = 100) -> list[dict[str, Any]]:
        fields = "id,text,username,timestamp,like_count,replies.limit(100){id,text,username,timestamp,like_count}"
        remaining = max(1, limit)
        cursor: str | None = None
        items: list[dict[str, Any]] = []
        while remaining > 0:
            params: dict[str, Any] = {"fields": fields, "limit": min(100, remaining)}
            if cursor:
                params["after"] = cursor
            payload = self._get(f"{media_id}/comments", params)
            page = payload.get("data", []) or []
            items.extend(page)
            remaining -= len(page)
            next_cursor = ((payload.get("paging") or {}).get("cursors") or {}).get("after")
            if not page or remaining <= 0 or not next_cursor:
                break
            cursor = str(next_cursor)
        return items[:limit]

    def get_mentioned_comment(self, ig_user_id: str, comment_id: str) -> dict[str, Any]:
        """A @mention webhook gives a media_id + comment_id on someone else's media;
        the account can only read it through its own edge."""
        fields = "mentioned_comment.comment_id(" + comment_id + "){id,text,username,timestamp,like_count}"
        return self._get(ig_user_id, {"fields": fields})


def verify_signature(app_secret: str, raw_body: bytes, header_signature: str | None) -> bool:
    """Validate Meta's X-Hub-Signature-256 header so only Meta can post to the webhook."""
    if not header_signature or not app_secret:
        return False
    prefix = "sha256="
    if not header_signature.startswith(prefix):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header_signature[len(prefix):])


def detect_account(access_token: str, *, graph_version: str = "v21.0") -> dict[str, Any]:
    """Given ONLY an access token, auto-detect the Instagram Business account it grants,
    the correct API base, and the best token to store. Tries three token shapes:
      1. Instagram-login (business login) token -> graph.instagram.com/me
      2. Facebook Page token -> /me?fields=instagram_business_account
      3. Facebook User token -> /me/accounts (pick a page with an IG account; store its
         long-lived PAGE token, which is what comment/media reads actually need)

    Returns {ig_user_id, username, api_base, access_token, page_id?} or raises
    InstagramApiError with a human-readable reason so the dashboard can show why a
    pasted token didn't work.
    """
    errors: list[str] = []

    def _try(url: str, params: dict) -> dict[str, Any] | None:
        try:
            r = httpx.get(url, params=params, timeout=20.0)
        except httpx.HTTPError as exc:
            errors.append(str(exc)[:120])
            return None
        if r.status_code >= 400:
            errors.append(f"{r.status_code}: {r.text[:120]}")
            return None
        return r.json()

    # 1) Instagram-login token
    data = _try(
        f"https://graph.instagram.com/{graph_version}/me",
        {"access_token": access_token, "fields": "user_id,username"},
    )
    if data:
        uid = str(data.get("user_id") or data.get("id") or "")
        if uid:
            return {
                "ig_user_id": uid,
                "username": data.get("username"),
                "api_base": "graph.instagram.com",
                "access_token": access_token,
            }

    fb = f"https://graph.facebook.com/{graph_version}"

    # 2) Page token
    data = _try(f"{fb}/me", {"access_token": access_token, "fields": "id,name,instagram_business_account{id,username}"})
    if data:
        iba = data.get("instagram_business_account") or {}
        if iba.get("id"):
            return {
                "ig_user_id": str(iba["id"]),
                "username": iba.get("username"),
                "api_base": "graph.facebook.com",
                "access_token": access_token,
                "page_id": str(data.get("id")) if data.get("id") else None,
            }

    # 3) User token -> pick a managed page that has an IG business account
    data = _try(
        f"{fb}/me/accounts",
        {"access_token": access_token, "fields": "name,access_token,instagram_business_account{id,username}", "limit": 50},
    )
    if data:
        for page in data.get("data", []) or []:
            iba = page.get("instagram_business_account") or {}
            if iba.get("id"):
                return {
                    "ig_user_id": str(iba["id"]),
                    "username": iba.get("username"),
                    "api_base": "graph.facebook.com",
                    "access_token": page.get("access_token") or access_token,
                    "page_id": None,
                }
        errors.append("hech bir sahifaga Instagram Business akkaunt ulanmagan")

    raise InstagramApiError(
        "Token'dan Instagram Business akkaunt aniqlanmadi. Sabab: " + " | ".join(errors[:3])
    )


def exchange_long_lived_token(app_id: str, app_secret: str, short_token: str, *, graph_version: str = "v21.0") -> dict[str, Any]:
    """Exchange a short-lived token for a ~60-day long-lived one."""
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short_token,
    }
    response = httpx.get(f"https://graph.facebook.com/{graph_version}/oauth/access_token", params=params, timeout=20.0)
    if response.status_code >= 400:
        raise InstagramApiError(f"Token exchange {response.status_code}: {response.text[:300]}", status_code=response.status_code)
    return response.json()

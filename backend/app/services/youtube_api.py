from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx


YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
CHANNEL_ID_RE = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
LEGACY_USERNAME_PREFIX = "user:"
SENSITIVE_QUERY_RE = re.compile(r"(?i)([?&](?:key|api_key|access_token)=)[^&\s]+")
RATE_LIMIT_REASONS = {
    "dailyLimitExceeded",
    "quotaExceeded",
    "rateLimitExceeded",
    "userRateLimitExceeded",
}


class YouTubeApiError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        reason: str | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.reason = reason
        self.retry_after_seconds = retry_after_seconds

    @property
    def rate_limited(self) -> bool:
        return self.status_code == 429 or self.reason in RATE_LIMIT_REASONS


@dataclass
class YouTubeRef:
    original: str
    kind: str
    ref: str
    video_id: str | None = None
    channel_id: str | None = None
    channel_handle: str | None = None
    query: str | None = None


def parse_youtube_ref(value: str) -> YouTubeRef:
    original = value.strip()
    if not original:
        raise ValueError("YouTube source bo'sh bo'lishi mumkin emas")

    candidate = original
    if candidate.startswith("#"):
        query = candidate.strip()
        return YouTubeRef(original=original, kind="hashtag", ref=query, query=query)
    if candidate.startswith("@"):
        if not re.fullmatch(r"@[^\s/]+", candidate):
            raise ValueError("YouTube handle @ belgisi bilan bitta qiymat bo'lishi kerak")
        handle = candidate.strip()
        return YouTubeRef(original=original, kind="channel", ref=handle.lower(), channel_handle=handle)
    if CHANNEL_ID_RE.fullmatch(candidate):
        return YouTubeRef(original=original, kind="channel", ref=candidate, channel_id=candidate)
    if VIDEO_ID_RE.fullmatch(candidate):
        return YouTubeRef(original=original, kind="video", ref=candidate, video_id=candidate)

    parsed = urlparse(candidate if re.match(r"^https?://", candidate) else f"https://{candidate}")
    host = parsed.netloc.lower().removeprefix("www.")
    path_parts = [part for part in parsed.path.split("/") if part]

    if host in {"youtu.be"} and path_parts and VIDEO_ID_RE.fullmatch(path_parts[0]):
        return YouTubeRef(original=original, kind="video", ref=path_parts[0], video_id=path_parts[0])

    if host == "youtube.com" or host.endswith(".youtube.com"):
        query_video_id = parse_qs(parsed.query).get("v", [None])[0]
        if query_video_id and VIDEO_ID_RE.fullmatch(query_video_id):
            return YouTubeRef(original=original, kind="video", ref=query_video_id, video_id=query_video_id)
        if len(path_parts) >= 2 and path_parts[0] in {"shorts", "embed", "live"} and VIDEO_ID_RE.fullmatch(path_parts[1]):
            return YouTubeRef(original=original, kind="video", ref=path_parts[1], video_id=path_parts[1])
        if path_parts and path_parts[0].startswith("@"):
            handle = path_parts[0]
            if not re.fullmatch(r"@[^\s/]+", handle):
                raise ValueError("YouTube handle @ belgisi bilan bitta qiymat bo'lishi kerak")
            return YouTubeRef(original=original, kind="channel", ref=handle.lower(), channel_handle=handle)
        if len(path_parts) >= 2 and path_parts[0] == "channel":
            channel_id = path_parts[1]
            if not CHANNEL_ID_RE.fullmatch(channel_id):
                raise ValueError("YouTube channel ID UC bilan boshlanadigan 24 belgili ID bo'lishi kerak")
            return YouTubeRef(original=original, kind="channel", ref=channel_id, channel_id=channel_id)
        if len(path_parts) >= 2 and path_parts[0] == "user":
            username = path_parts[1]
            return YouTubeRef(
                original=original,
                kind="channel",
                ref=f"{LEGACY_USERNAME_PREFIX}{username.lower()}",
            )
        if len(path_parts) >= 2 and path_parts[0] == "c":
            raise ValueError("YouTube /c/... custom URL qo'llanmaydi. @handle yoki /channel/UC... linkdan foydalaning")

    query = original.strip()
    return YouTubeRef(original=original, kind="keyword", ref=query.lower(), query=query)


def parse_rfc3339(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class YouTubeApi:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("YOUTUBE_API_KEY sozlanmagan")
        merged_params = {**params, "key": self.api_key}
        try:
            response = httpx.get(f"{YOUTUBE_API_BASE}/{path}", params=merged_params, timeout=25)
        except httpx.RequestError:
            raise YouTubeApiError(f"YouTube API {path} request failed (network error)") from None
        if response.is_error:
            raise build_youtube_api_error(path, response, api_key=self.api_key)
        try:
            return response.json()
        except ValueError:
            raise YouTubeApiError(f"YouTube API {path} returned invalid JSON") from None

    def channel_by_handle(self, handle: str) -> dict[str, Any] | None:
        if handle.lower().startswith(LEGACY_USERNAME_PREFIX):
            return self.channel_by_username(handle[len(LEGACY_USERNAME_PREFIX):])
        payload = self.get(
            "channels",
            {"part": "snippet,statistics,contentDetails", "forHandle": handle.lstrip("@"), "maxResults": 1},
        )
        return first_item(payload)

    def channel_by_username(self, username: str) -> dict[str, Any] | None:
        payload = self.get(
            "channels",
            {"part": "snippet,statistics,contentDetails", "forUsername": username, "maxResults": 1},
        )
        return first_item(payload)

    def channel_by_id(self, channel_id: str) -> dict[str, Any] | None:
        payload = self.get(
            "channels",
            {"part": "snippet,statistics,contentDetails", "id": channel_id, "maxResults": 1},
        )
        return first_item(payload)

    def video_by_id(self, video_id: str) -> dict[str, Any] | None:
        payload = self.get(
            "videos",
            {"part": "snippet,statistics,contentDetails", "id": video_id, "maxResults": 1},
        )
        return first_item(payload)

    def search_videos(
        self,
        *,
        query: str | None = None,
        channel_id: str | None = None,
        published_after: datetime | None = None,
        page_token: str | None = None,
        max_results: int = 25,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "part": "snippet",
            "type": "video",
            "order": "date",
            "maxResults": max(1, min(50, max_results)),
        }
        if query:
            params["q"] = query
        if channel_id:
            params["channelId"] = channel_id
        if published_after:
            params["publishedAfter"] = published_after.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        if page_token:
            params["pageToken"] = page_token
        return self.get("search", params)

    def playlist_items(
        self,
        playlist_id: str,
        *,
        page_token: str | None = None,
        max_results: int = 50,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "part": "snippet,contentDetails",
            "playlistId": playlist_id,
            "maxResults": max(1, min(50, max_results)),
        }
        if page_token:
            params["pageToken"] = page_token
        return self.get("playlistItems", params)

    def video_comments(
        self,
        video_id: str,
        *,
        page_token: str | None = None,
        max_results: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "part": "snippet,replies",
            "videoId": video_id,
            "order": "time",
            "textFormat": "plainText",
            "maxResults": max(1, min(100, max_results)),
        }
        if page_token:
            params["pageToken"] = page_token
        return self.get("commentThreads", params)

    def channel_comments(
        self,
        channel_id: str,
        *,
        page_token: str | None = None,
        max_results: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "part": "snippet,replies",
            "allThreadsRelatedToChannelId": channel_id,
            "order": "time",
            "textFormat": "plainText",
            "maxResults": max(1, min(100, max_results)),
        }
        if page_token:
            params["pageToken"] = page_token
        return self.get("commentThreads", params)


def first_item(payload: dict[str, Any]) -> dict[str, Any] | None:
    items = payload.get("items") or []
    return items[0] if items else None


def build_youtube_api_error(path: str, response: httpx.Response, *, api_key: str = "") -> YouTubeApiError:
    reason = youtube_error_reason(response)
    if reason and api_key and api_key in reason:
        reason = None
    retry_after_seconds = parse_retry_after(response.headers.get("Retry-After"))
    suffix = f", reason={reason}" if reason else ""
    return YouTubeApiError(
        f"YouTube API {path} request failed (HTTP {response.status_code}{suffix})",
        status_code=response.status_code,
        reason=reason,
        retry_after_seconds=retry_after_seconds,
    )


def youtube_error_reason(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    error = payload.get("error") if isinstance(payload, dict) else None
    errors = error.get("errors") if isinstance(error, dict) else None
    reason = errors[0].get("reason") if isinstance(errors, list) and errors and isinstance(errors[0], dict) else None
    if not isinstance(reason, str):
        return None
    cleaned = re.sub(r"[^A-Za-z0-9_.-]", "", reason)[:64]
    return cleaned or None


def parse_retry_after(value: str | None) -> int | None:
    try:
        parsed = int(value or "")
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def safe_youtube_error(exc: Exception, *, api_key: str = "") -> str:
    if isinstance(exc, YouTubeApiError):
        return str(exc)
    message = " ".join(str(exc).split())
    if api_key:
        message = message.replace(api_key, "[REDACTED]")
    message = SENSITIVE_QUERY_RE.sub(r"\1[REDACTED]", message)
    return (message or type(exc).__name__)[:500]


def video_url(video_id: str | None) -> str | None:
    return f"https://www.youtube.com/watch?v={video_id}" if video_id else None


def comment_url(video_id: str | None, comment_id: str | None) -> str | None:
    if not video_id:
        return None
    if not comment_id:
        return video_url(video_id)
    return f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}"

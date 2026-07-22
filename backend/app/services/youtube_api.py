from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Iterator
from urllib.parse import parse_qs, urlparse

import httpx


logger = logging.getLogger("youtube-api")

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
# videos.list accepts up to 50 comma-separated ids for the same 1-unit cost as one id.
VIDEO_DETAIL_BATCH = 50
# The daily quota window resets at midnight US/Pacific, not UTC.
QUOTA_RESET_UTC_OFFSET_HOURS = 8
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
# These burn the whole daily allowance — backing off for an hour just re-fails.
# The only thing that clears them is the midnight-Pacific quota reset.
DAILY_QUOTA_REASONS = {"dailyLimitExceeded", "quotaExceeded"}


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

    @property
    def quota_exceeded(self) -> bool:
        """The daily unit allowance is gone; nothing works until the quota resets."""
        return self.reason in DAILY_QUOTA_REASONS

    @property
    def retryable(self) -> bool:
        """Transient: a network blip or a server-side 5xx, worth another attempt."""
        return self.status_code is None or self.status_code >= 500


def seconds_until_quota_reset(now: datetime | None = None) -> int:
    """Seconds until the next midnight US/Pacific, when the daily quota resets.

    Uses a fixed -8 offset rather than a tz database lookup: during daylight saving
    the estimate is an hour late, which only ever means waiting slightly longer than
    necessary — never retrying too early and burning the fresh allowance on 403s.
    """
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    pacific = moment - timedelta(hours=QUOTA_RESET_UTC_OFFSET_HOURS)
    next_midnight = (pacific + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(60, int((next_midnight - pacific).total_seconds()))


def chunked(values: Iterable[str], size: int) -> Iterator[list[str]]:
    batch: list[str] = []
    for value in values:
        batch.append(value)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


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
    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 25.0,
        max_attempts: int = 3,
        backoff_seconds: float = 1.0,
    ) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.max_attempts = max(1, max_attempts)
        self.backoff_seconds = backoff_seconds
        self._client: httpx.Client | None = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    @property
    def client(self) -> httpx.Client:
        """One pooled client per instance — a cycle makes dozens of calls and a
        fresh TCP+TLS handshake for each is pure latency."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=YOUTUBE_API_BASE,
                timeout=self.timeout,
                limits=httpx.Limits(max_keepalive_connections=4, max_connections=8),
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "YouTubeApi":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise YouTubeApiError("YOUTUBE_API_KEY sozlanmagan")
        merged_params = {**params, "key": self.api_key}
        last_error: YouTubeApiError | None = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self.client.get(f"/{path}", params=merged_params)
            except httpx.RequestError as exc:
                last_error = YouTubeApiError(
                    f"YouTube API {path} request failed (network error: {type(exc).__name__})"
                )
            else:
                if not response.is_error:
                    try:
                        return response.json()
                    except ValueError:
                        raise YouTubeApiError(f"YouTube API {path} returned invalid JSON") from None
                last_error = build_youtube_api_error(path, response, api_key=self.api_key)
                # Quota/rate limits are not transient at this timescale, and 4xx
                # means the request itself is wrong — retrying either just wastes units.
                if not last_error.retryable:
                    raise last_error

            if attempt < self.max_attempts:
                delay = self.backoff_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "YouTube API %s attempt %s/%s failed (%s); retrying in %.1fs",
                    path,
                    attempt,
                    self.max_attempts,
                    last_error,
                    delay,
                )
                time.sleep(delay)

        raise last_error or YouTubeApiError(f"YouTube API {path} request failed")

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
        return self.videos_by_ids([video_id]).get(video_id)

    def videos_by_ids(self, video_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
        """Fetch details for many videos in 50-id batches, keyed by video id.

        One batched call costs the same single unit as one id, so this turns the
        per-video N+1 into ceil(n/50) calls.
        """
        unique_ids = list(dict.fromkeys(video_id for video_id in video_ids if video_id))
        details: dict[str, dict[str, Any]] = {}
        for batch in chunked(unique_ids, VIDEO_DETAIL_BATCH):
            payload = self.get(
                "videos",
                {
                    "part": "snippet,statistics,contentDetails",
                    "id": ",".join(batch),
                    "maxResults": len(batch),
                },
            )
            for item in payload.get("items") or []:
                item_id = item.get("id")
                if isinstance(item_id, str):
                    details[item_id] = item
        return details

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

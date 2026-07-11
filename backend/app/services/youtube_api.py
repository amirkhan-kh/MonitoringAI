from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx


YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


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
        handle = candidate.strip()
        return YouTubeRef(original=original, kind="channel", ref=handle.lower(), channel_handle=handle)
    if VIDEO_ID_RE.fullmatch(candidate):
        return YouTubeRef(original=original, kind="video", ref=candidate, video_id=candidate)

    parsed = urlparse(candidate if re.match(r"^https?://", candidate) else f"https://{candidate}")
    host = parsed.netloc.lower().removeprefix("www.")
    path_parts = [part for part in parsed.path.split("/") if part]

    if host in {"youtu.be"} and path_parts and VIDEO_ID_RE.fullmatch(path_parts[0]):
        return YouTubeRef(original=original, kind="video", ref=path_parts[0], video_id=path_parts[0])

    if host.endswith("youtube.com"):
        query_video_id = parse_qs(parsed.query).get("v", [None])[0]
        if query_video_id and VIDEO_ID_RE.fullmatch(query_video_id):
            return YouTubeRef(original=original, kind="video", ref=query_video_id, video_id=query_video_id)
        if len(path_parts) >= 2 and path_parts[0] in {"shorts", "embed", "live"} and VIDEO_ID_RE.fullmatch(path_parts[1]):
            return YouTubeRef(original=original, kind="video", ref=path_parts[1], video_id=path_parts[1])
        if path_parts and path_parts[0].startswith("@"):
            handle = path_parts[0]
            return YouTubeRef(original=original, kind="channel", ref=handle.lower(), channel_handle=handle)
        if len(path_parts) >= 2 and path_parts[0] == "channel":
            channel_id = path_parts[1]
            return YouTubeRef(original=original, kind="channel", ref=channel_id, channel_id=channel_id)
        if len(path_parts) >= 2 and path_parts[0] in {"c", "user"}:
            query = path_parts[1]
            return YouTubeRef(original=original, kind="keyword", ref=query.lower(), query=query)

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
        response = httpx.get(f"{YOUTUBE_API_BASE}/{path}", params=merged_params, timeout=25)
        response.raise_for_status()
        return response.json()

    def channel_by_handle(self, handle: str) -> dict[str, Any] | None:
        payload = self.get(
            "channels",
            {"part": "snippet,statistics,contentDetails", "forHandle": handle.lstrip("@"), "maxResults": 1},
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


def video_url(video_id: str | None) -> str | None:
    return f"https://www.youtube.com/watch?v={video_id}" if video_id else None


def comment_url(video_id: str | None, comment_id: str | None) -> str | None:
    if not video_id:
        return None
    if not comment_id:
        return video_url(video_id)
    return f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}"

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
from fastapi import HTTPException
from pydantic import ValidationError

from app.main import enrich_youtube_source, import_youtube_sources, upsert_youtube_source
from app.models import YouTubeSource
from app.schemas import YouTubeSourceImport
from app.services.youtube_api import YouTubeApi, YouTubeApiError, parse_youtube_ref, safe_youtube_error


class YouTubeRefParserTests(unittest.TestCase):
    def test_supported_reference_matrix(self) -> None:
        cases = (
            ("UCY3nNF2MUDKHrELA6LzbnHA", "channel", "UCY3nNF2MUDKHrELA6LzbnHA"),
            ("https://www.youtube.com/channel/UCY3nNF2MUDKHrELA6LzbnHA", "channel", "UCY3nNF2MUDKHrELA6LzbnHA"),
            ("@uzummarket", "channel", "@uzummarket"),
            ("https://www.youtube.com/@uzummarket/videos", "channel", "@uzummarket"),
            ("https://www.youtube.com/user/LegacyBrand", "channel", "user:legacybrand"),
            ("dQw4w9WgXcQ", "video", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ", "video", "dQw4w9WgXcQ"),
        )

        for value, expected_kind, expected_ref in cases:
            with self.subTest(value=value):
                parsed = parse_youtube_ref(value)
                self.assertEqual(parsed.kind, expected_kind)
                self.assertEqual(parsed.ref, expected_ref)

    def test_custom_c_url_is_explicitly_unsupported(self) -> None:
        with self.assertRaisesRegex(ValueError, "@handle"):
            parse_youtube_ref("https://www.youtube.com/c/UzumMarket")

    def test_channel_url_rejects_invalid_channel_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "24 belgili"):
            parse_youtube_ref("https://www.youtube.com/channel/not-a-channel-id")

    def test_channel_parser_rejects_fake_domains_and_invalid_handles(self) -> None:
        self.assertEqual(parse_youtube_ref("https://evilyoutube.com/@brand").kind, "keyword")
        for value in ("@", "@brand/extra", "https://youtube.com/@"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "handle"):
                    parse_youtube_ref(value)

    def test_legacy_user_url_resolves_with_for_username(self) -> None:
        api = YouTubeApi("secret-youtube-api-key")
        with patch.object(api, "get", return_value={"items": [{"id": "channel-id"}]}) as get:
            item = api.channel_by_handle("user:legacybrand")

        self.assertEqual(item, {"id": "channel-id"})
        get.assert_called_once_with(
            "channels",
            {
                "part": "snippet,statistics,contentDetails",
                "forUsername": "legacybrand",
                "maxResults": 1,
            },
        )


class YouTubeApiErrorTests(unittest.TestCase):
    def test_http_error_does_not_expose_api_key(self) -> None:
        api_key = "secret-youtube-api-key"
        request = httpx.Request(
            "GET",
            f"https://www.googleapis.com/youtube/v3/search?part=snippet&key={api_key}",
        )
        response = httpx.Response(
            429,
            request=request,
            headers={"Retry-After": "90"},
            json={"error": {"errors": [{"reason": "quotaExceeded"}]}},
        )

        with patch("httpx.Client.get", return_value=response):
            with self.assertRaises(YouTubeApiError) as raised:
                YouTubeApi(api_key).get("search", {"part": "snippet"})

        error = raised.exception
        self.assertNotIn(api_key, str(error))
        self.assertNotIn("key=", str(error))
        self.assertEqual(error.status_code, 429)
        self.assertEqual(error.retry_after_seconds, 90)
        self.assertTrue(error.rate_limited)

    def test_network_error_does_not_expose_request_url(self) -> None:
        api_key = "secret-youtube-api-key"
        request = httpx.Request(
            "GET",
            f"https://www.googleapis.com/youtube/v3/videos?key={api_key}",
        )

        with patch(
            "httpx.Client.get",
            side_effect=httpx.ConnectTimeout("timed out", request=request),
        ):
            with self.assertRaises(YouTubeApiError) as raised:
                YouTubeApi(api_key, max_attempts=1).get("videos", {"id": "abcdefghijk"})

        self.assertEqual(
            str(raised.exception),
            "YouTube API videos request failed (network error: ConnectTimeout)",
        )
        self.assertNotIn(api_key, str(raised.exception))

    def test_api_key_is_not_echoed_if_remote_reason_contains_it(self) -> None:
        api_key = "secret-youtube-api-key"
        request = httpx.Request("GET", "https://www.googleapis.com/youtube/v3/search")
        response = httpx.Response(
            403,
            request=request,
            json={"error": {"errors": [{"reason": api_key}]}},
        )

        with patch("httpx.Client.get", return_value=response):
            with self.assertRaises(YouTubeApiError) as raised:
                YouTubeApi(api_key).get("search", {"part": "snippet"})

        self.assertNotIn(api_key, str(raised.exception))

    def test_fallback_sanitizer_redacts_sensitive_query_values(self) -> None:
        api_key = "secret-youtube-api-key"
        error = RuntimeError(
            f"request failed: https://example.test/path?part=snippet&key={api_key}&access_token=other-secret"
        )

        message = safe_youtube_error(error, api_key=api_key)

        self.assertNotIn(api_key, message)
        self.assertNotIn("other-secret", message)
        self.assertIn("key=[REDACTED]", message)
        self.assertIn("access_token=[REDACTED]", message)


class YouTubeImportInvariantTests(unittest.TestCase):
    def test_import_requires_brand_id(self) -> None:
        with self.assertRaises(ValidationError):
            YouTubeSourceImport(raw_text="@brand")

    def test_import_rejects_unknown_brand(self) -> None:
        session = MagicMock()
        session.get.return_value = None
        payload = YouTubeSourceImport(brand_id=uuid.uuid4(), raw_text="@brand")

        with self.assertRaises(HTTPException) as raised:
            import_youtube_sources(payload, session)

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail, "Brand not found")

    def test_official_channel_mode_rejects_non_channel_refs(self) -> None:
        for ref in ("dQw4w9WgXcQ", "brand review"):
            with self.subTest(ref=ref):
                with self.assertRaisesRegex(ValueError, "faqat kanal"):
                    upsert_youtube_source(
                        MagicMock(),
                        ref=ref,
                        brand_id=uuid.uuid4(),
                        source_category="owned",
                        monitoring_mode="all_messages",
                        nickname=None,
                        competitor_name=None,
                        hashtags=[],
                        notes=None,
                        collect_videos=True,
                        collect_comments=True,
                        collect_transcripts=False,
                        monitor_from=datetime.now(timezone.utc),
                        official_channel_only=True,
                    )

    def test_enrichment_rejects_missing_channel_and_video(self) -> None:
        api = YouTubeApi("configured-api-key")
        channel = YouTubeSource(source_ref="@missing", source_kind="channel", channel_handle="@missing")
        video = YouTubeSource(source_ref="dQw4w9WgXcQ", source_kind="video", video_id="dQw4w9WgXcQ")

        with patch.object(api, "channel_by_handle", return_value=None):
            with self.assertRaisesRegex(ValueError, "kanal topilmadi"):
                enrich_youtube_source(channel, api)
        with patch.object(api, "video_by_id", return_value=None):
            with self.assertRaisesRegex(ValueError, "video topilmadi"):
                enrich_youtube_source(video, api)


if __name__ == "__main__":
    unittest.main()

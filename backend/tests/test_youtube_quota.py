from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import httpx

from app.db import SessionLocal, init_db
from app.main import (
    YouTubeIngestCache,
    comment_page_is_older_than,
    ingest_youtube_comment,
    resolve_youtube_mention_row,
    upsert_youtube_source,
    youtube_source_is_resolved,
    youtube_sync_window,
)
from app.models import Brand, YouTubeMention, YouTubeSource
from app.services.youtube_api import (
    YouTubeApi,
    YouTubeApiError,
    seconds_until_quota_reset,
)
from app.workers.youtube_worker import is_due


def response_for(payload: dict, status_code: int = 200) -> httpx.Response:
    request = httpx.Request("GET", "https://www.googleapis.com/youtube/v3/videos")
    return httpx.Response(status_code, request=request, json=payload)


class RetryTests(unittest.TestCase):
    def test_transient_network_error_is_retried_then_succeeds(self) -> None:
        request = httpx.Request("GET", "https://www.googleapis.com/youtube/v3/videos")
        outcomes = [
            httpx.ConnectTimeout("timed out", request=request),
            response_for({"items": [{"id": "abcdefghijk"}]}),
        ]

        def fake_get(*_args, **_kwargs):
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        with patch("httpx.Client.get", side_effect=fake_get):
            payload = YouTubeApi("k", max_attempts=3, backoff_seconds=0).get("videos", {"id": "x"})

        self.assertEqual(payload["items"][0]["id"], "abcdefghijk")
        self.assertEqual(outcomes, [])

    def test_server_error_is_retried_up_to_max_attempts(self) -> None:
        response = response_for({"error": {"errors": [{"reason": "backendError"}]}}, status_code=503)

        with patch("httpx.Client.get", return_value=response) as mocked:
            with self.assertRaises(YouTubeApiError) as raised:
                YouTubeApi("k", max_attempts=3, backoff_seconds=0).get("videos", {"id": "x"})

        self.assertEqual(mocked.call_count, 3)
        self.assertTrue(raised.exception.retryable)

    def test_quota_error_is_not_retried(self) -> None:
        response = response_for({"error": {"errors": [{"reason": "quotaExceeded"}]}}, status_code=403)

        with patch("httpx.Client.get", return_value=response) as mocked:
            with self.assertRaises(YouTubeApiError) as raised:
                YouTubeApi("k", max_attempts=3, backoff_seconds=0).get("videos", {"id": "x"})

        # Retrying a spent quota only collects more 403s.
        self.assertEqual(mocked.call_count, 1)
        self.assertTrue(raised.exception.quota_exceeded)
        self.assertTrue(raised.exception.rate_limited)
        self.assertFalse(raised.exception.retryable)

    def test_rate_limit_without_daily_quota_is_not_flagged_as_quota_exceeded(self) -> None:
        response = response_for({"error": {"errors": [{"reason": "rateLimitExceeded"}]}}, status_code=403)

        with patch("httpx.Client.get", return_value=response):
            with self.assertRaises(YouTubeApiError) as raised:
                YouTubeApi("k", max_attempts=1).get("videos", {"id": "x"})

        self.assertTrue(raised.exception.rate_limited)
        self.assertFalse(raised.exception.quota_exceeded)


class VideoBatchTests(unittest.TestCase):
    def test_fifty_ids_cost_a_single_call(self) -> None:
        video_ids = [f"vid{index:08d}" for index in range(50)]
        response = response_for({"items": [{"id": video_id} for video_id in video_ids]})

        with patch("httpx.Client.get", return_value=response) as mocked:
            details = YouTubeApi("k").videos_by_ids(video_ids)

        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(len(details), 50)
        sent_ids = mocked.call_args.kwargs["params"]["id"]
        self.assertEqual(sent_ids.split(","), video_ids)

    def test_more_than_fifty_ids_are_split_into_batches(self) -> None:
        video_ids = [f"vid{index:08d}" for index in range(120)]

        with patch("httpx.Client.get", return_value=response_for({"items": []})) as mocked:
            YouTubeApi("k").videos_by_ids(video_ids)

        self.assertEqual(mocked.call_count, 3)

    def test_duplicate_and_empty_ids_are_dropped(self) -> None:
        with patch("httpx.Client.get", return_value=response_for({"items": []})) as mocked:
            YouTubeApi("k").videos_by_ids(["a", "a", "", None, "b"])

        self.assertEqual(mocked.call_args.kwargs["params"]["id"], "a,b")

    def test_missing_video_is_absent_rather_than_raising(self) -> None:
        with patch("httpx.Client.get", return_value=response_for({"items": []})):
            details = YouTubeApi("k").videos_by_ids(["gone"])

        self.assertEqual(details, {})


class QuotaResetTests(unittest.TestCase):
    def test_reset_wait_is_never_longer_than_a_day(self) -> None:
        moment = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
        self.assertLessEqual(seconds_until_quota_reset(moment), 24 * 3600)

    def test_just_after_reset_waits_almost_a_full_day(self) -> None:
        # 08:05 UTC is 00:05 Pacific under the fixed -8 offset.
        moment = datetime(2026, 7, 20, 8, 5, tzinfo=timezone.utc)
        wait = seconds_until_quota_reset(moment)
        self.assertGreater(wait, 23 * 3600)

    def test_just_before_reset_waits_only_minutes(self) -> None:
        moment = datetime(2026, 7, 20, 7, 50, tzinfo=timezone.utc)
        self.assertLess(seconds_until_quota_reset(moment), 900)


class SyncWindowTests(unittest.TestCase):
    def make_source(self, **kwargs) -> YouTubeSource:
        defaults = {
            "source_ref": "@example",
            "source_kind": "channel",
            "created_at": datetime(2026, 7, 1, tzinfo=timezone.utc),
            "monitor_from": None,
            "last_checked_at": None,
        }
        defaults.update(kwargs)
        return YouTubeSource(**defaults)

    def test_first_sync_backfills_from_the_floor(self) -> None:
        source = self.make_source(monitor_from=datetime(2026, 7, 10, tzinfo=timezone.utc))
        window = youtube_sync_window(source, overlap_seconds=900)

        self.assertTrue(window.first_sync)
        self.assertEqual(window.since, datetime(2026, 7, 10, tzinfo=timezone.utc))
        self.assertEqual(window.since, window.floor)

    def test_later_sync_starts_from_the_checkpoint_minus_overlap(self) -> None:
        source = self.make_source(
            monitor_from=datetime(2026, 7, 1, tzinfo=timezone.utc),
            last_checked_at=datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc),
        )
        window = youtube_sync_window(source, overlap_seconds=900)

        self.assertFalse(window.first_sync)
        self.assertEqual(window.since, datetime(2026, 7, 20, 11, 45, tzinfo=timezone.utc))

    def test_overlap_never_reaches_back_past_the_floor(self) -> None:
        floor = datetime(2026, 7, 20, 11, 55, tzinfo=timezone.utc)
        source = self.make_source(
            monitor_from=floor,
            last_checked_at=datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc),
        )
        window = youtube_sync_window(source, overlap_seconds=3600)

        self.assertEqual(window.since, floor)

    def test_naive_timestamps_are_treated_as_utc(self) -> None:
        source = self.make_source(last_checked_at=datetime(2026, 7, 20, 12, 0))
        window = youtube_sync_window(source, overlap_seconds=0)

        self.assertEqual(window.since, datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc))


class EnrichmentSkipTests(unittest.TestCase):
    def test_resolved_channel_needs_no_further_api_calls(self) -> None:
        source = YouTubeSource(
            source_ref="@example",
            source_kind="channel",
            channel_id="UC" + "x" * 22,
            uploads_playlist_id="UU" + "x" * 22,
        )
        self.assertTrue(youtube_source_is_resolved(source))

    def test_channel_missing_uploads_playlist_is_re_enriched(self) -> None:
        source = YouTubeSource(source_ref="@example", source_kind="channel", channel_id="UC" + "x" * 22)
        self.assertFalse(youtube_source_is_resolved(source))

    def test_video_source_needs_its_title(self) -> None:
        source = YouTubeSource(source_ref="dQw4w9WgXcQ", source_kind="video", video_id="dQw4w9WgXcQ")
        self.assertFalse(youtube_source_is_resolved(source))
        source.title = "Some video"
        self.assertTrue(youtube_source_is_resolved(source))


class CommentPaginationTests(unittest.TestCase):
    def thread(self, published_at: str) -> dict:
        return {"snippet": {"topLevelComment": {"snippet": {"publishedAt": published_at}}}}

    def test_page_entirely_before_the_window_stops_pagination(self) -> None:
        since = datetime(2026, 7, 20, tzinfo=timezone.utc)
        items = [self.thread("2026-07-19T10:00:00Z"), self.thread("2026-07-18T10:00:00Z")]
        self.assertTrue(comment_page_is_older_than(items, since))

    def test_page_with_one_fresh_thread_keeps_paginating(self) -> None:
        since = datetime(2026, 7, 20, tzinfo=timezone.utc)
        items = [self.thread("2026-07-21T10:00:00Z"), self.thread("2026-07-18T10:00:00Z")]
        self.assertFalse(comment_page_is_older_than(items, since))

    def test_unparseable_timestamp_keeps_paginating(self) -> None:
        since = datetime(2026, 7, 20, tzinfo=timezone.utc)
        self.assertFalse(comment_page_is_older_than([self.thread("not-a-date")], since))

    def test_no_window_never_stops_early(self) -> None:
        self.assertFalse(comment_page_is_older_than([self.thread("2020-01-01T00:00:00Z")], None))


class SearchThrottleTests(unittest.TestCase):
    def make_source(self, kind: str, last_checked_at: datetime | None) -> YouTubeSource:
        return YouTubeSource(source_ref="x", source_kind=kind, last_checked_at=last_checked_at)

    def test_channel_source_is_always_due(self) -> None:
        now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
        source = self.make_source("channel", now - timedelta(seconds=5))
        self.assertTrue(is_due(source, now=now, min_interval_seconds=3600))

    def test_search_source_waits_out_its_interval(self) -> None:
        now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
        source = self.make_source("keyword", now - timedelta(seconds=600))
        self.assertFalse(is_due(source, now=now, min_interval_seconds=3600))

    def test_search_source_runs_once_the_interval_elapsed(self) -> None:
        now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
        source = self.make_source("hashtag", now - timedelta(seconds=3601))
        self.assertTrue(is_due(source, now=now, min_interval_seconds=3600))

    def test_never_synced_search_source_runs_immediately(self) -> None:
        now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
        self.assertTrue(is_due(self.make_source("keyword", None), now=now, min_interval_seconds=3600))


class InCycleDedupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init_db()

    def setUp(self) -> None:
        self.session = SessionLocal()
        self.brand = Brand(name=f"YouTube dedup {uuid.uuid4().hex}")
        self.session.add(self.brand)
        self.session.flush()
        self.source = upsert_youtube_source(
            self.session,
            ref="@dedup-channel",
            brand_id=self.brand.id,
            source_category="owned",
            monitoring_mode="all_messages",
            nickname=None,
            competitor_name=None,
            notes=None,
            monitor_from=None,
            hashtags=[],
            collect_videos=True,
            collect_comments=True,
            collect_transcripts=False,
            api=None,
        )
        self.session.flush()

    def tearDown(self) -> None:
        self.session.rollback()
        self.session.close()

    def test_same_external_id_twice_in_one_cycle_reuses_the_pending_row(self) -> None:
        cache = YouTubeIngestCache()
        external_id = "youtube:comment:dup-1"

        first = resolve_youtube_mention_row(
            self.session,
            brand_id=self.brand.id,
            external_id=external_id,
            item_type="comment",
            cache=cache,
        )
        second = resolve_youtube_mention_row(
            self.session,
            brand_id=self.brand.id,
            external_id=external_id,
            item_type="comment",
            cache=cache,
        )

        self.assertIs(first, second)

    def test_duplicate_comment_in_one_cycle_commits_without_integrity_error(self) -> None:
        cache = YouTubeIngestCache()
        snippet = {
            "textDisplay": "great product",
            "authorDisplayName": "Someone",
            "publishedAt": "2026-07-20T10:00:00Z",
        }
        for _ in range(2):
            ingest_youtube_comment(
                self.session,
                self.source,
                comment_id="dup-comment-1",
                video_id="vid00000001",
                snippet=snippet,
                raw={},
                item_type="comment",
                cache=cache,
            )

        # Without the cache this raises IntegrityError and the whole cycle is lost.
        self.session.flush()

        rows = (
            self.session.query(YouTubeMention)
            .filter(
                YouTubeMention.brand_id == self.brand.id,
                YouTubeMention.external_id == "youtube:comment:dup-comment-1",
            )
            .all()
        )
        self.assertEqual(len(rows), 1)


class FakeYouTubeApi:
    """A 50-video channel, so the batching and watermark wins are measurable."""

    def __init__(self, video_count: int = 50) -> None:
        self.api_key = "fake"
        self.calls: list[str] = []
        self.videos = [
            {
                "id": f"vid{index:08d}",
                "snippet": {
                    "title": f"Video {index}",
                    "description": "desc",
                    "publishedAt": f"2026-07-{(index % 28) + 1:02d}T10:00:00Z",
                    "channelId": "UC" + "x" * 22,
                    "channelTitle": "Example",
                },
                "statistics": {},
            }
            for index in range(video_count)
        ]

    @property
    def configured(self) -> bool:
        return True

    def playlist_items(self, _playlist_id, *, page_token=None, max_results=50):
        self.calls.append("playlistItems")
        return {
            "items": [
                {"snippet": {"resourceId": {"videoId": video["id"]}, "publishedAt": video["snippet"]["publishedAt"]}}
                for video in self.videos
            ]
        }

    def videos_by_ids(self, video_ids):
        ids = [video_id for video_id in dict.fromkeys(video_ids) if video_id]
        # Mirrors the real 50-per-call batching.
        for _ in range(0, max(len(ids), 1), 50):
            self.calls.append("videos")
        return {video["id"]: video for video in self.videos if video["id"] in set(ids)}

    def channel_comments(self, _channel_id, *, page_token=None, max_results=100):
        self.calls.append("commentThreads")
        return {"items": []}


class SyncCallBudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init_db()

    def setUp(self) -> None:
        self.session = SessionLocal()
        self.brand = Brand(name=f"YouTube budget {uuid.uuid4().hex}")
        self.session.add(self.brand)
        self.session.flush()
        self.source = YouTubeSource(
            brand_id=self.brand.id,
            source_ref=f"@budget-{uuid.uuid4().hex[:8]}",
            source_kind="channel",
            source_category="owned",
            monitoring_mode="all_messages",
            channel_id="UC" + "x" * 22,
            uploads_playlist_id="UU" + "x" * 22,
            collect_videos=True,
            collect_comments=True,
            monitor_from=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        self.session.add(self.source)
        self.session.flush()

    def tearDown(self) -> None:
        # sync_youtube_source commits internally, so a rollback is not enough to
        # undo what these tests create — delete the rows explicitly.
        self.session.rollback()
        self.session.query(YouTubeMention).filter(YouTubeMention.source_id == self.source.id).delete(
            synchronize_session=False
        )
        self.session.query(YouTubeSource).filter(YouTubeSource.id == self.source.id).delete(
            synchronize_session=False
        )
        self.session.query(Brand).filter(Brand.id == self.brand.id).delete(synchronize_session=False)
        self.session.commit()
        self.session.close()

    def sync(self, api: FakeYouTubeApi):
        from app.main import sync_youtube_source
        from app.schemas import YouTubeSourceSyncRequest

        return sync_youtube_source(
            self.session, self.source, api, YouTubeSourceSyncRequest(max_pages=1, comments_per_video=100)
        )

    def test_fifty_videos_take_one_batched_detail_call_not_fifty(self) -> None:
        api = FakeYouTubeApi(video_count=50)
        result = self.sync(api)

        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.videos_seen, 50)
        # Pre-batching this was 50 separate videos.list calls.
        self.assertEqual(api.calls.count("videos"), 1)
        self.assertEqual(len(api.calls), 3)

    def test_second_cycle_rediscovers_nothing_and_makes_no_detail_call(self) -> None:
        self.sync(FakeYouTubeApi(video_count=50))

        second = FakeYouTubeApi(video_count=50)
        result = self.sync(second)

        self.assertTrue(result.ok, result.error)
        # The watermark moved past every video, so none are re-fetched.
        self.assertEqual(result.videos_seen, 0)
        self.assertEqual(second.calls.count("videos"), 0)

    def test_checkpoint_is_recorded_so_the_next_cycle_is_incremental(self) -> None:
        self.assertIsNone(self.source.last_checked_at)
        self.sync(FakeYouTubeApi(video_count=5))
        self.assertIsNotNone(self.source.last_checked_at)

    def test_single_video_source_is_fetched_once_not_twice(self) -> None:
        self.source.source_kind = "video"
        self.source.video_id = "vid00000003"
        self.source.title = "Already resolved"
        self.source.collect_comments = False
        self.session.flush()

        api = FakeYouTubeApi(video_count=5)
        result = self.sync(api)

        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.videos_seen, 1)
        # Discovery must not resolve the video itself — the batch call already does.
        self.assertEqual(api.calls.count("videos"), 1)

    def test_a_failed_cycle_leaves_the_checkpoint_untouched(self) -> None:
        class BrokenApi(FakeYouTubeApi):
            def playlist_items(self, *args, **kwargs):
                raise YouTubeApiError("boom", status_code=500)

        result = self.sync(BrokenApi())

        self.assertFalse(result.ok)
        # Advancing the watermark on failure would silently skip that window forever.
        self.assertIsNone(self.source.last_checked_at)


if __name__ == "__main__":
    unittest.main()

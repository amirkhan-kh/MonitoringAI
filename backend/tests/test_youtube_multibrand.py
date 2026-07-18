from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from sqlalchemy import inspect

from app.db import SessionLocal, engine, init_db
from app.main import ingest_youtube_comment, ingest_youtube_video, upsert_youtube_source
from app.models import Brand, YouTubeMention, YouTubeSource


class YouTubeMultiBrandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init_db()
        init_db()

    def setUp(self) -> None:
        self.session = SessionLocal()
        suffix = uuid.uuid4().hex
        self.brand_a = Brand(name=f"YouTube isolation A {suffix}")
        self.brand_b = Brand(name=f"YouTube isolation B {suffix}")
        self.session.add_all([self.brand_a, self.brand_b])
        self.session.flush()

    def tearDown(self) -> None:
        self.session.rollback()
        self.session.close()

    def create_source(self, brand: Brand, ref: str = "@shared-channel") -> YouTubeSource:
        source = upsert_youtube_source(
            self.session,
            ref=ref,
            brand_id=brand.id,
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
        )
        self.session.flush()
        return source

    def test_schema_upgrade_is_idempotent_and_brand_scoped(self) -> None:
        constraints_by_table = {
            table_name: {
                constraint["name"]: tuple(constraint.get("column_names") or ())
                for constraint in inspect(engine).get_unique_constraints(table_name)
            }
            for table_name in ("youtube_sources", "youtube_mentions")
        }

        self.assertEqual(
            constraints_by_table["youtube_sources"].get("uq_youtube_sources_brand_source_ref"),
            ("brand_id", "source_ref"),
        )
        self.assertNotIn("uq_youtube_sources_source_ref", constraints_by_table["youtube_sources"])
        self.assertEqual(
            constraints_by_table["youtube_mentions"].get("uq_youtube_mentions_brand_external_id"),
            ("brand_id", "external_id"),
        )
        self.assertNotIn("uq_youtube_mentions_external_id", constraints_by_table["youtube_mentions"])

    def test_same_source_ref_isolated_per_brand(self) -> None:
        source_a = self.create_source(self.brand_a)
        source_b = self.create_source(self.brand_b)
        source_a_again = self.create_source(self.brand_a)

        self.assertNotEqual(source_a.id, source_b.id)
        self.assertEqual(source_a.id, source_a_again.id)
        self.assertEqual(source_a.brand_id, self.brand_a.id)
        self.assertEqual(source_b.brand_id, self.brand_b.id)
        self.assertEqual(
            self.session.query(YouTubeSource).filter(YouTubeSource.source_ref == "@shared-channel").count(),
            2,
        )

    def test_same_video_external_id_does_not_move_between_brands(self) -> None:
        source_a = self.create_source(self.brand_a)
        source_b = self.create_source(self.brand_b)
        item = {
            "id": "abcdefghijk",
            "snippet": {
                "title": "Shared public video",
                "description": "Same video monitored by two brands",
                "channelId": "shared-channel-id",
                "channelTitle": "Shared Channel",
                "publishedAt": "2026-07-17T00:00:00Z",
            },
            "statistics": {"viewCount": "10", "likeCount": "2", "commentCount": "1"},
        }

        mention_a = ingest_youtube_video(self.session, source_a, item)
        self.session.flush()
        mention_b = ingest_youtube_video(self.session, source_b, item)
        self.session.flush()
        mention_a_again = ingest_youtube_video(self.session, source_a, item)
        self.session.flush()

        self.assertIsNotNone(mention_a)
        self.assertIsNotNone(mention_b)
        self.assertNotEqual(mention_a.id, mention_b.id)
        self.assertEqual(mention_a.id, mention_a_again.id)
        self.assertEqual((mention_a.brand_id, mention_a.source_id), (self.brand_a.id, source_a.id))
        self.assertEqual((mention_b.brand_id, mention_b.source_id), (self.brand_b.id, source_b.id))
        self.assertEqual(
            self.session.query(YouTubeMention)
            .filter(YouTubeMention.external_id == "youtube:video:abcdefghijk")
            .count(),
            2,
        )

    def test_same_comment_external_id_does_not_move_between_brands(self) -> None:
        source_a = self.create_source(self.brand_a)
        source_b = self.create_source(self.brand_b)
        snippet = {
            "textDisplay": "Shared public comment",
            "authorDisplayName": "Viewer",
            "likeCount": 3,
            "publishedAt": "2026-07-17T00:00:00Z",
        }

        mention_a = ingest_youtube_comment(
            self.session,
            source_a,
            comment_id="shared-comment-id",
            video_id="abcdefghijk",
            snippet=snippet,
            raw={"id": "shared-comment-id"},
        )
        self.session.flush()
        mention_b = ingest_youtube_comment(
            self.session,
            source_b,
            comment_id="shared-comment-id",
            video_id="abcdefghijk",
            snippet=snippet,
            raw={"id": "shared-comment-id"},
        )
        self.session.flush()

        self.assertIsNotNone(mention_a)
        self.assertIsNotNone(mention_b)
        self.assertNotEqual(mention_a.id, mention_b.id)
        self.assertEqual((mention_a.brand_id, mention_a.source_id), (self.brand_a.id, source_a.id))
        self.assertEqual((mention_b.brand_id, mention_b.source_id), (self.brand_b.id, source_b.id))
        self.assertEqual(
            self.session.query(YouTubeMention)
            .filter(YouTubeMention.external_id == "youtube:comment:shared-comment-id")
            .count(),
            2,
        )


if __name__ == "__main__":
    unittest.main()

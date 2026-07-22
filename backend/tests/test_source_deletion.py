from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from app.db import SessionLocal, init_db

# main.py keeps its own copies of the upsert helpers (the service module has near-identical
# twins used by the Telegram bot commands). The API — and therefore the UI's "add source"
# flow — goes through these, so the revive path must be asserted against main's versions.
from app.main import delete_telegram_source, upsert_telegram_source_from_chat
from app.models import Analysis, Brand, Mention, TelegramSource
from app.services.telegram_command_agent import (
    upsert_telegram_source_from_chat as agent_upsert_telegram_source_from_chat,
)


class SourceDeletionModeTests(unittest.TestCase):
    """Deleting a source must offer a choice: keep the analysed mentions, or purge them.

    Keeping them is the recovery path for an accidental delete, so it has to survive a
    later re-add without paying for a second AI analysis of the same messages.
    """

    @classmethod
    def setUpClass(cls) -> None:
        init_db()

    def setUp(self) -> None:
        self.brand_ids: list[uuid.UUID] = []

    def tearDown(self) -> None:
        with SessionLocal() as session:
            mention_ids = [
                row[0]
                for row in session.query(Mention.id).filter(Mention.brand_id.in_(self.brand_ids)).all()
            ]
            if mention_ids:
                session.query(Analysis).filter(Analysis.mention_id.in_(mention_ids)).delete(
                    synchronize_session=False
                )
            session.query(Mention).filter(Mention.brand_id.in_(self.brand_ids)).delete(synchronize_session=False)
            session.query(TelegramSource).filter(TelegramSource.brand_id.in_(self.brand_ids)).delete(
                synchronize_session=False
            )
            session.query(Brand).filter(Brand.id.in_(self.brand_ids)).delete(synchronize_session=False)
            session.commit()

    def create_brand(self) -> uuid.UUID:
        with SessionLocal() as session:
            brand = Brand(name=f"Deletion test {uuid.uuid4()}")
            session.add(brand)
            session.commit()
            self.brand_ids.append(brand.id)
            return brand.id

    def seed_source_with_analysed_mention(self, brand_id: uuid.UUID, chat_id: int) -> tuple[uuid.UUID, uuid.UUID]:
        with SessionLocal() as session:
            source = TelegramSource(
                brand_id=brand_id,
                chat_id=chat_id,
                username="deletion_test_channel",
                title="Deletion test",
                source_kind="channel",
                last_seen_message_id=500,
            )
            session.add(source)
            session.commit()
            mention = Mention(
                brand_id=brand_id,
                source_id=source.id,
                platform="telegram",
                source_type="channel_post",
                chat_id=chat_id,
                message_id=500,
                normalized_text="deletion test post",
                brand_match_terms=[],
                raw={},
                message_date=datetime.now(timezone.utc),
            )
            session.add(mention)
            session.commit()
            session.add(Analysis(mention_id=mention.id, model_name="test-model"))
            session.commit()
            return source.id, mention.id

    def test_purge_removes_mentions_and_analyses(self) -> None:
        brand_id = self.create_brand()
        source_id, mention_id = self.seed_source_with_analysed_mention(brand_id, chat_id=-100777001)

        with SessionLocal() as session:
            result = delete_telegram_source(source_id, session, purge_mentions=True)

        self.assertFalse(result["soft_deleted"])
        self.assertEqual(result["mentions_deleted"], 1)
        self.assertEqual(result["analyses_deleted"], 1)
        with SessionLocal() as session:
            self.assertIsNone(session.get(TelegramSource, source_id))
            self.assertIsNone(session.get(Mention, mention_id))
            self.assertEqual(
                session.query(Analysis).filter(Analysis.mention_id == mention_id).count(), 0
            )

    def test_keeping_mentions_soft_deletes_the_source(self) -> None:
        brand_id = self.create_brand()
        source_id, mention_id = self.seed_source_with_analysed_mention(brand_id, chat_id=-100777002)

        with SessionLocal() as session:
            result = delete_telegram_source(source_id, session, purge_mentions=False)

        self.assertTrue(result["soft_deleted"])
        self.assertEqual(result["mentions_retained"], 1)
        self.assertEqual(result["mentions_deleted"], 0)
        with SessionLocal() as session:
            source = session.get(TelegramSource, source_id)
            self.assertIsNotNone(source, "row must survive so the mention keeps a valid source_id")
            self.assertIsNotNone(source.deleted_at)
            self.assertFalse(source.active)
            # The mention and its verdict are exactly what the operator asked to keep.
            self.assertIsNotNone(session.get(Mention, mention_id))
            self.assertEqual(
                session.query(Analysis).filter(Analysis.mention_id == mention_id).count(), 1
            )

    def test_soft_deleted_source_is_hidden_from_listing(self) -> None:
        from app.main import list_telegram_sources

        brand_id = self.create_brand()
        source_id, _ = self.seed_source_with_analysed_mention(brand_id, chat_id=-100777003)
        with SessionLocal() as session:
            delete_telegram_source(source_id, session, purge_mentions=False)
        with SessionLocal() as session:
            listed = {source.id for source in list_telegram_sources(session)}
        self.assertNotIn(source_id, listed)

    def test_re_adding_revives_the_row_so_nothing_is_re_analysed(self) -> None:
        # Both copies of the helper must revive, otherwise re-adding through one entry point
        # leaves the row soft-deleted and the source stays invisible for good.
        implementations = {
            "main (API / UI add-source)": upsert_telegram_source_from_chat,
            "telegram_command_agent (bot commands)": agent_upsert_telegram_source_from_chat,
        }
        for index, (label, upsert) in enumerate(implementations.items()):
            with self.subTest(implementation=label):
                brand_id = self.create_brand()
                chat_id = -100777004 - index
                source_id, mention_id = self.seed_source_with_analysed_mention(brand_id, chat_id=chat_id)
                with SessionLocal() as session:
                    delete_telegram_source(source_id, session, purge_mentions=False)

                with SessionLocal() as session:
                    revived = upsert(
                        session,
                        chat_info={
                            "id": chat_id,
                            "username": "deletion_test_channel",
                            "type": "channel",
                            "title": "Deletion test",
                        },
                        brand_id=brand_id,
                        source_category="owned",
                        monitoring_mode="all_messages",
                        competitor_name=None,
                        notes=None,
                        collect_posts=True,
                        collect_comments=True,
                    )
                    session.commit()
                    self.assertEqual(revived.id, source_id, "re-add must reuse the row, not create a new one")
                    self.assertIsNone(revived.deleted_at)
                    self.assertTrue(revived.active)
                    # The watermark survives, so catch-up resumes at the gap instead of re-importing.
                    self.assertEqual(revived.last_seen_message_id, 500)

                with SessionLocal() as session:
                    # The already-analysed mention is still attached and still has its verdict,
                    # so the AI worker's "no analysis yet" gate will not pick it up again.
                    mention = session.get(Mention, mention_id)
                    self.assertIsNotNone(mention)
                    self.assertEqual(mention.source_id, source_id)
                    self.assertEqual(
                        session.query(Analysis).filter(Analysis.mention_id == mention_id).count(), 1
                    )

    def test_source_listing_hides_only_deleted_not_paused(self) -> None:
        """A paused source (active=False) must still be listed; a deleted one must not."""
        from app.main import list_telegram_sources

        brand_id = self.create_brand()
        paused_id, _ = self.seed_source_with_analysed_mention(brand_id, chat_id=-100777010)
        with SessionLocal() as session:
            session.get(TelegramSource, paused_id).active = False
            session.commit()
        with SessionLocal() as session:
            listed = {source.id for source in list_telegram_sources(session)}
        self.assertIn(paused_id, listed)


if __name__ == "__main__":
    unittest.main()

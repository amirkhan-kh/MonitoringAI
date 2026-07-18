from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.config import Settings
from app.services.telegram_api import TelegramBotApi, TelegramPollingConflictError
from app.services.telegram_command_agent import handle_command_update
from app.services.telegram_ingestion import (
    TelegramSourceOwnershipError,
    ensure_telegram_source_owner,
    upsert_linked_discussion_source,
)
from app.workers.telegram_backfill import backfill_comments
from app.workers.telegram_worker import exclusive_polling_lock


class FakeBotApi:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []

    def send_message(self, chat_id: int, text: str) -> None:
        self.messages.append((chat_id, text))


class FakeSessionContext:
    def __enter__(self) -> object:
        return object()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None


class FakeMessage:
    def __init__(self, discussion_entity: object) -> None:
        self.id = 201
        self.chat = discussion_entity
        self.reply_to = SimpleNamespace(reply_to_msg_id=101)

    async def get_chat(self) -> object:
        return self.chat


class FakeTelegramClient:
    def __init__(self, message: FakeMessage) -> None:
        self.message = message

    async def iter_messages(self, entity: object, *, reply_to: int, limit: int):
        yield self.message


class TelegramCommandSecurityTests(unittest.TestCase):
    def test_command_allowlist_parses_csv_and_json(self) -> None:
        csv_settings = Settings(_env_file=None, telegram_command_allowed_user_ids="123, 456")
        json_settings = Settings(_env_file=None, telegram_command_allowed_user_ids="[789, 101112]")
        scalar_settings = Settings(_env_file=None, telegram_command_allowed_user_ids=131415)

        self.assertEqual(csv_settings.telegram_command_allowed_user_ids, [123, 456])
        self.assertEqual(json_settings.telegram_command_allowed_user_ids, [789, 101112])
        self.assertEqual(scalar_settings.telegram_command_allowed_user_ids, [131415])

    def test_private_command_is_rejected_when_allowlist_is_empty(self) -> None:
        api = FakeBotApi()
        update = {
            "message": {
                "chat": {"id": 42, "type": "private"},
                "from": {"id": 777},
                "text": "/help",
            }
        }

        with patch(
            "app.services.telegram_command_agent.get_settings",
            return_value=SimpleNamespace(telegram_command_allowed_user_ids=[]),
        ):
            handled = handle_command_update(api, MagicMock(), update)

        self.assertTrue(handled)
        self.assertEqual(api.messages, [(42, "Bu agent komandalarini ishlatishga ruxsatingiz yo'q.")])

    def test_private_command_is_allowed_for_configured_sender(self) -> None:
        api = FakeBotApi()
        update = {
            "message": {
                "chat": {"id": 42, "type": "private"},
                "from": {"id": 777},
                "text": "/help",
            }
        }

        with patch(
            "app.services.telegram_command_agent.get_settings",
            return_value=SimpleNamespace(telegram_command_allowed_user_ids=[777]),
        ):
            handled = handle_command_update(api, MagicMock(), update)

        self.assertTrue(handled)
        self.assertIn("MonitoringAI agent komandalar", api.messages[0][1])


class TelegramPollingTests(unittest.TestCase):
    def test_polling_conflict_does_not_leak_bot_token(self) -> None:
        response = MagicMock()
        response.status_code = 409
        response.reason_phrase = "Conflict"
        response.json.return_value = {
            "ok": False,
            "error_code": 409,
            "description": "Conflict: terminated by other getUpdates request",
        }
        client = MagicMock()
        client.__enter__.return_value.post.return_value = response

        with patch("app.services.telegram_api.httpx.Client", return_value=client):
            with self.assertRaises(TelegramPollingConflictError) as raised:
                TelegramBotApi("secret-bot-token").get_updates(offset=None, timeout=1, allowed_updates=[])

        self.assertNotIn("secret-bot-token", str(raised.exception))
        self.assertEqual(raised.exception.status_code, 409)

    def test_network_error_does_not_leak_bot_token(self) -> None:
        token = "secret-bot-token"
        request = httpx.Request("POST", f"https://api.telegram.org/bot{token}/getUpdates")
        client = MagicMock()
        client.__enter__.return_value.post.side_effect = httpx.ConnectTimeout("timed out", request=request)

        with patch("app.services.telegram_api.httpx.Client", return_value=client):
            with self.assertRaisesRegex(RuntimeError, "Telegram API getUpdates failed \\(0\\): network error") as raised:
                TelegramBotApi(token).get_updates(offset=None, timeout=1, allowed_updates=[])

        self.assertNotIn(token, str(raised.exception))

    def test_only_one_local_poller_can_hold_the_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock_file = str(Path(directory) / "telegram.lock")
            with exclusive_polling_lock(lock_file):
                with self.assertRaises(RuntimeError):
                    with exclusive_polling_lock(lock_file):
                        self.fail("A second polling worker acquired the same lock")


class TelegramDiscussionTests(unittest.TestCase):
    def test_discussion_source_inherits_parent_monitoring_config(self) -> None:
        parent = SimpleNamespace(
            brand_id="brand-id",
            source_category="owned",
            monitoring_mode="all_messages",
            competitor_name=None,
            collect_comments=True,
            monitor_from="2026-07-17",
            active=True,
            linked_discussion_chat_id=None,
        )
        discussion = SimpleNamespace(
            brand_id=None,
            source_category="unknown",
            monitoring_mode="brand_matches_only",
            competitor_name=None,
            collect_posts=True,
            collect_comments=False,
            monitor_from=None,
            active=False,
        )

        with (
            patch("app.services.telegram_ingestion.source_for_chat", return_value=parent),
            patch("app.services.telegram_ingestion.upsert_telegram_source", return_value=discussion),
        ):
            result = upsert_linked_discussion_source(
                MagicMock(),
                parent_chat={"id": -1001},
                discussion_chat={"id": -1002},
            )

        self.assertIs(result, discussion)
        self.assertEqual(parent.linked_discussion_chat_id, -1002)
        self.assertEqual(discussion.brand_id, "brand-id")
        self.assertFalse(discussion.collect_posts)
        self.assertTrue(discussion.collect_comments)
        self.assertTrue(discussion.active)


class TelegramMultiBrandSafetyTests(unittest.TestCase):
    def test_existing_source_cannot_be_silently_reassigned(self) -> None:
        source = SimpleNamespace(brand_id="brand-a")

        with self.assertRaises(TelegramSourceOwnershipError):
            ensure_telegram_source_owner(source, "brand-b")

        self.assertEqual(source.brand_id, "brand-a")

    def test_existing_source_accepts_same_owner(self) -> None:
        source = SimpleNamespace(brand_id="brand-a")

        ensure_telegram_source_owner(source, "brand-a")

    def test_linked_discussion_cannot_move_between_brands(self) -> None:
        parent = SimpleNamespace(brand_id="brand-a")
        discussion = SimpleNamespace(brand_id="brand-b")

        with (
            patch("app.services.telegram_ingestion.source_for_chat", return_value=parent),
            patch("app.services.telegram_ingestion.upsert_telegram_source", return_value=discussion),
        ):
            with self.assertRaises(TelegramSourceOwnershipError):
                upsert_linked_discussion_source(
                    MagicMock(),
                    parent_chat={"id": -1001},
                    discussion_chat={"id": -1002},
                )


class TelegramDiscussionBackfillTests(unittest.IsolatedAsyncioTestCase):
    async def test_comment_is_ingested_under_discussion_chat(self) -> None:
        parent_chat = {"id": -1001, "type": "channel", "title": "Brand channel"}
        discussion_chat = {"id": -1002, "type": "supergroup", "title": "Brand discussion"}
        discussion_entity = object()
        comment = FakeMessage(discussion_entity)
        client = FakeTelegramClient(comment)
        ingest = MagicMock()

        with (
            patch("app.workers.telegram_backfill.Message", FakeMessage),
            patch("app.workers.telegram_backfill.entity_to_chat_dict", new=AsyncMock(return_value=discussion_chat)),
            patch(
                "app.workers.telegram_backfill.telethon_message_to_dict",
                return_value={"message_id": comment.id, "text": "Comment"},
            ),
            patch("app.workers.telegram_backfill.SessionLocal", return_value=FakeSessionContext()),
            patch("app.workers.telegram_backfill.ingest_telethon_message", ingest),
        ):
            count = await backfill_comments(
                client,
                entity=object(),
                chat=parent_chat,
                post=SimpleNamespace(id=55),
                limit=10,
            )

        self.assertEqual(count, 1)
        ingest.assert_called_once()
        call = ingest.call_args
        self.assertEqual(call.kwargs["chat"], discussion_chat)
        self.assertEqual(call.kwargs["parent_chat"], parent_chat)
        self.assertEqual(call.kwargs["source_type"], "comment")
        self.assertEqual(call.kwargs["message"]["discussion_message_id"], 55)


if __name__ == "__main__":
    unittest.main()

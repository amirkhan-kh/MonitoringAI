from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from cryptography.fernet import Fernet
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import inspect

from app.db import SessionLocal, engine, init_db
from app.main import (
    backfill_telegram_source,
    build_access_status,
    check_brand_telegram_source_access,
    delete_telegram_source,
    normalize_chat_ref,
    refresh_telegram_source,
    setup_brand_telegram,
    telegram_setup_response,
    update_telegram_source,
)
from app.models import Brand, Mention, TelegramBotConnection, TelegramSource
from app.schemas import TelegramSourceBackfillRequest, TelegramSourceUpdate, TelegramSetupRequest
from app.services.telegram_api import TelegramBotApi, TelegramBotApiError
from app.services.telegram_connector import (
    ConnectorEncryptionError,
    decrypt_bot_token,
    encrypt_bot_token,
    ingest_connector_update,
    normalize_bot_username,
)
from app.services.telegram_ingestion import ingest_telethon_message, should_skip_source_message
from app.workers.telegram_connector_worker import handle_poll_error
from app.workers.telegram_connector_worker import poll_connection
from app.workers.telegram_live_sync import active_sources_for_chat, set_telethon_access_status
from app.workers.telegram_worker import polling_transport_available


class FakeTelegramApi:
    def __init__(
        self,
        *,
        bot_id: int = 9001,
        username: str = "brand_monitoring_bot",
        webhook_url: str = "",
        chats: dict[object, dict] | None = None,
        member_status: str = "administrator",
        can_read_all_group_messages: bool = True,
    ) -> None:
        self.bot_id = bot_id
        self.username = username
        self.webhook_url = webhook_url
        self.chats = chats or {}
        self.member_status = member_status
        self.can_read_all_group_messages = can_read_all_group_messages

    def get_me(self) -> dict:
        return {
            "id": self.bot_id,
            "username": self.username,
            "is_bot": True,
            "can_read_all_group_messages": self.can_read_all_group_messages,
        }

    def get_webhook_info(self) -> dict:
        return {"url": self.webhook_url}

    def get_chat(self, ref: object) -> dict | None:
        return self.chats.get(ref)

    def get_chat_member(self, chat_id: object, user_id: int) -> dict:
        return {"status": self.member_status, "user": {"id": user_id}}


class TelegramConnectorCryptoTests(unittest.TestCase):
    def test_token_round_trip_requires_stable_fernet_key(self) -> None:
        key = Fernet.generate_key().decode("ascii")
        token = "123456:secret-telegram-token"
        encrypted = encrypt_bot_token(token, key=key)

        self.assertNotIn(token, encrypted)
        self.assertEqual(decrypt_bot_token(encrypted, key=key), token)
        with self.assertRaises(ConnectorEncryptionError):
            decrypt_bot_token(encrypted, key=Fernet.generate_key().decode("ascii"))

    def test_setup_schema_requires_at_least_one_reference(self) -> None:
        with self.assertRaises(ValidationError):
            TelegramSetupRequest()

    def test_bot_link_normalization_accepts_collectible_username_and_rejects_invalid_ref(self) -> None:
        self.assertEqual(normalize_bot_username("https://t.me/Brand_Monitoring_Bot"), "Brand_Monitoring_Bot")
        self.assertEqual(normalize_bot_username("https://t.me/BrandSupport"), "BrandSupport")
        with self.assertRaises(ValueError):
            normalize_bot_username("https://t.me/not/valid")

    def test_private_invite_requires_numeric_chat_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "-100"):
            normalize_chat_ref("https://t.me/+privateInviteHash")
        self.assertEqual(normalize_chat_ref("-1001234567890"), -1001234567890)


class TelegramApiConnectorTests(unittest.TestCase):
    def test_retry_after_is_typed_and_token_is_not_exposed(self) -> None:
        token = "secret-bot-token"
        response = MagicMock()
        response.status_code = 429
        response.reason_phrase = "Too Many Requests"
        response.json.return_value = {
            "ok": False,
            "error_code": 429,
            "description": f"retry {token}",
            "parameters": {"retry_after": 17},
        }
        client = MagicMock()
        client.__enter__.return_value.post.return_value = response

        with patch("app.services.telegram_api.httpx.Client", return_value=client):
            with self.assertRaises(TelegramBotApiError) as raised:
                TelegramBotApi(token).get_updates(offset=None, timeout=0, allowed_updates=[])

        self.assertEqual(raised.exception.retry_after_seconds, 17)
        self.assertNotIn(token, str(raised.exception))

    def test_legacy_worker_never_deletes_active_webhook(self) -> None:
        api = MagicMock()
        api.get_webhook_info.return_value = {"url": "https://brand.example/telegram"}

        self.assertFalse(polling_transport_available(api))
        api.delete_webhook.assert_not_called()

    def test_admin_bot_can_read_group_even_with_privacy_mode_enabled(self) -> None:
        api = FakeTelegramApi(
            member_status="administrator",
            can_read_all_group_messages=False,
            chats={
                "@brand_group": {
                    "id": -100555001,
                    "username": "brand_group",
                    "title": "Brand group",
                    "type": "supergroup",
                }
            },
        )

        access, _ = build_access_status(api, "@brand_group")

        self.assertTrue(access.can_read_comments)
        self.assertTrue(access.ok)


class TelegramConnectorIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init_db()

    def setUp(self) -> None:
        self.key = Fernet.generate_key().decode("ascii")
        self.brand_ids: list[uuid.UUID] = []

    def tearDown(self) -> None:
        with SessionLocal() as session:
            session.query(Mention).filter(Mention.brand_id.in_(self.brand_ids)).delete(synchronize_session=False)
            session.query(TelegramSource).filter(TelegramSource.brand_id.in_(self.brand_ids)).delete(
                synchronize_session=False
            )
            session.query(TelegramBotConnection).filter(
                TelegramBotConnection.brand_id.in_(self.brand_ids)
            ).delete(synchronize_session=False)
            session.query(Brand).filter(Brand.id.in_(self.brand_ids)).delete(synchronize_session=False)
            session.commit()

    def create_brand(self) -> uuid.UUID:
        with SessionLocal() as session:
            brand = Brand(name=f"Connector test {uuid.uuid4()}")
            session.add(brand)
            session.commit()
            session.refresh(brand)
            self.brand_ids.append(brand.id)
            return brand.id

    def test_schema_migration_is_idempotent_and_brand_scoped(self) -> None:
        init_db()
        db_inspector = inspect(engine)
        source_indexes = {
            index["name"]: tuple(index.get("column_names") or ())
            for index in db_inspector.get_indexes("telegram_sources")
        }
        mention_constraints = {
            constraint["name"]: tuple(constraint.get("column_names") or ())
            for constraint in db_inspector.get_unique_constraints("mentions")
        }
        connection_constraints = {
            constraint["name"]: tuple(constraint.get("column_names") or ())
            for constraint in db_inspector.get_unique_constraints("telegram_bot_connections")
        }

        self.assertEqual(
            source_indexes.get("uq_telegram_sources_brand_chat_id"),
            ("brand_id", "chat_id"),
        )
        self.assertEqual(
            source_indexes.get("uq_telegram_sources_brand_username"),
            ("brand_id", "username"),
        )
        self.assertEqual(
            mention_constraints.get("uq_mentions_brand_source_chat_message"),
            ("brand_id", "source_id", "platform", "chat_id", "message_id"),
        )
        self.assertEqual(
            connection_constraints.get("uq_telegram_bot_connections_bot_id"),
            ("bot_id",),
        )

    def settings(self, *, global_token: str = "") -> SimpleNamespace:
        return SimpleNamespace(
            telegram_bot_token=global_token,
            telegram_api_id=None,
            telegram_api_hash="",
            telegram_poll_conflict_backoff_seconds=300,
            telegram_connector_error_backoff_seconds=30,
            telegram_allowed_updates=["message", "channel_post"],
        )

    def setup_with_api(
        self,
        brand_id: uuid.UUID,
        payload: TelegramSetupRequest,
        api: FakeTelegramApi,
        *,
        global_token: str = "",
    ):
        with (
            patch("app.main.get_settings", return_value=self.settings(global_token=global_token)),
            patch(
                "app.services.telegram_connector.get_settings",
                return_value=SimpleNamespace(connector_encryption_key=self.key),
            ),
            patch("app.main.TelegramBotApi", return_value=api),
            SessionLocal() as session,
        ):
            return setup_brand_telegram(brand_id, payload, session)

    def test_setup_encrypts_token_links_sources_and_never_returns_secret(self) -> None:
        brand_id = self.create_brand()
        token = "9001:brand-secret-token"
        channel_id = -1001001
        discussion_id = -1001002
        api = FakeTelegramApi(
            chats={
                "@brand_channel": {
                    "id": channel_id,
                    "username": "brand_channel",
                    "title": "Brand channel",
                    "type": "channel",
                    "linked_chat_id": discussion_id,
                },
                "@brand_discussion": {
                    "id": discussion_id,
                    "username": "brand_discussion",
                    "title": "Brand discussion",
                    "type": "supergroup",
                },
            }
        )
        payload = TelegramSetupRequest(
            bot_link="@brand_monitoring_bot",
            bot_token=token,
            bot_mode="polling",
            channel_ref="@brand_channel",
            discussion_ref="@brand_discussion",
            monitor_from="2026-07-01",
        )

        response = self.setup_with_api(brand_id, payload, api)
        serialized = response.model_dump_json()

        self.assertNotIn(token, serialized)
        self.assertTrue(response.connection.token_configured)
        roles = {source.source_role: source for source in response.sources}
        self.assertEqual(roles["discussion"].parent_source_id, roles["channel"].id)
        self.assertEqual(roles["channel"].linked_discussion_chat_id, discussion_id)
        with SessionLocal() as session:
            connection = session.query(TelegramBotConnection).filter_by(brand_id=brand_id).one()
            self.assertNotEqual(connection.token_ciphertext, token)
            self.assertEqual(decrypt_bot_token(connection.token_ciphertext, key=self.key), token)

    def test_polling_rejects_existing_webhook_and_global_consumer(self) -> None:
        brand_id = self.create_brand()
        token = "9002:conflicting-secret-token"
        payload = TelegramSetupRequest(bot_token=token, bot_mode="polling")

        with self.assertRaises(HTTPException) as webhook_error:
            self.setup_with_api(
                brand_id,
                payload,
                FakeTelegramApi(bot_id=9002, webhook_url="https://brand.example/hook"),
            )
        self.assertEqual(webhook_error.exception.status_code, 409)

        with self.assertRaises(HTTPException) as global_error:
            self.setup_with_api(
                brand_id,
                payload,
                FakeTelegramApi(bot_id=9002),
                global_token=token,
            )
        self.assertEqual(global_error.exception.status_code, 409)

    def test_link_only_connection_is_reference_and_inbox_is_inactive(self) -> None:
        brand_id = self.create_brand()
        response = self.setup_with_api(
            brand_id,
            TelegramSetupRequest(bot_link="@reference_only_bot"),
            FakeTelegramApi(username="reference_only_bot"),
        )

        self.assertFalse(response.connection.token_configured)
        self.assertEqual(response.connection.mode, "reference")
        inbox = next(source for source in response.sources if source.source_role == "bot_inbox")
        self.assertFalse(inbox.active)
        self.assertIn("bot_link_is_reference_only_without_token", response.warnings)

    def test_replacing_token_resets_persisted_cursor(self) -> None:
        brand_id = self.create_brand()
        first = TelegramSetupRequest(bot_token="9003:first-secret", bot_mode="reference")
        second = TelegramSetupRequest(bot_token="9003:second-secret", bot_mode="reference")
        api = FakeTelegramApi(bot_id=9003)

        self.setup_with_api(brand_id, first, api)
        with SessionLocal() as session:
            connection = session.query(TelegramBotConnection).filter_by(brand_id=brand_id).one()
            connection.last_update_id = 999
            session.commit()

        self.setup_with_api(brand_id, second, api)
        with SessionLocal() as session:
            connection = session.query(TelegramBotConnection).filter_by(brand_id=brand_id).one()
            self.assertIsNone(connection.last_update_id)

    def test_public_channel_without_bot_admin_is_not_monitoring_ready(self) -> None:
        brand_id = self.create_brand()
        api = FakeTelegramApi(
            member_status="left",
            chats={
                "@public_brand": {
                    "id": -1004401,
                    "username": "public_brand",
                    "title": "Public brand",
                    "type": "channel",
                }
            },
        )
        response = self.setup_with_api(
            brand_id,
            TelegramSetupRequest(
                bot_token="9441:not-admin-secret",
                bot_mode="polling",
                channel_ref="@public_brand",
            ),
            api,
        )

        channel = next(source for source in response.sources if source.source_role == "channel")
        self.assertEqual(channel.bot_access_status, "denied")
        self.assertFalse(response.capabilities.channel_monitoring)
        self.assertIn("channel_bot_access_denied", response.warnings)

    def test_global_reference_sources_remain_on_legacy_worker(self) -> None:
        brand_id = self.create_brand()
        token = "9442:global-worker-secret"
        response = self.setup_with_api(
            brand_id,
            TelegramSetupRequest(
                bot_token=token,
                bot_mode="reference",
                channel_ref="@legacy_brand",
            ),
            FakeTelegramApi(
                bot_id=9442,
                chats={
                    "@legacy_brand": {
                        "id": -1004402,
                        "username": "legacy_brand",
                        "title": "Legacy brand",
                        "type": "channel",
                    }
                },
            ),
            global_token=token,
        )

        channel = next(source for source in response.sources if source.source_role == "channel")
        self.assertIsNone(channel.bot_connection_id)
        self.assertEqual(response.connection.status, "legacy")
        self.assertTrue(response.capabilities.channel_monitoring)
        self.assertIn("global_bot_uses_legacy_worker", response.warnings)

    def test_token_only_rotation_rebinds_dedicated_source_to_global_worker(self) -> None:
        brand_id = self.create_brand()
        chat_id = -1004410
        initial = self.setup_with_api(
            brand_id,
            TelegramSetupRequest(
                bot_token="9450:dedicated-worker-secret",
                bot_mode="polling",
                channel_ref="@rotation_channel",
            ),
            FakeTelegramApi(
                bot_id=9450,
                chats={
                    "@rotation_channel": {
                        "id": chat_id,
                        "username": "rotation_channel",
                        "title": "Rotation channel",
                        "type": "channel",
                    }
                },
            ),
        )
        initial_channel = next(source for source in initial.sources if source.source_role == "channel")
        self.assertEqual(initial_channel.bot_connection_id, initial.connection.id)

        global_token = "9451:global-worker-secret"
        rotated = self.setup_with_api(
            brand_id,
            TelegramSetupRequest(bot_token=global_token),
            FakeTelegramApi(
                bot_id=9451,
                member_status="left",
                chats={
                    chat_id: {
                        "id": chat_id,
                        "username": "rotation_channel",
                        "title": "Rotation channel",
                        "type": "channel",
                    }
                },
            ),
            global_token=global_token,
        )
        rotated_channel = next(source for source in rotated.sources if source.source_role == "channel")

        self.assertEqual(rotated_channel.id, initial_channel.id)
        self.assertIsNone(rotated_channel.bot_connection_id)
        self.assertEqual(rotated_channel.bot_access_status, "denied")
        self.assertIsNotNone(rotated_channel.access_checked_at)
        self.assertEqual(rotated.connection.status, "legacy")
        self.assertIn("global_bot_uses_legacy_worker", rotated.warnings)
        self.assertIn("channel_bot_access_denied", rotated.warnings)
        with SessionLocal() as session:
            inbox = (
                session.query(TelegramSource)
                .filter_by(brand_id=brand_id, source_role="bot_inbox")
                .one()
            )
            self.assertFalse(inbox.active)
            self.assertFalse(inbox.connector_managed)
            self.assertIsNone(inbox.bot_connection_id)

    def test_token_only_rotation_rebinds_global_source_to_dedicated_connection(self) -> None:
        brand_id = self.create_brand()
        chat_id = -1004411
        global_token = "9452:global-worker-secret"
        initial = self.setup_with_api(
            brand_id,
            TelegramSetupRequest(
                bot_token=global_token,
                channel_ref="@reverse_rotation_channel",
            ),
            FakeTelegramApi(
                bot_id=9452,
                chats={
                    "@reverse_rotation_channel": {
                        "id": chat_id,
                        "username": "reverse_rotation_channel",
                        "title": "Reverse rotation channel",
                        "type": "channel",
                    }
                },
            ),
            global_token=global_token,
        )
        initial_channel = next(source for source in initial.sources if source.source_role == "channel")
        self.assertIsNone(initial_channel.bot_connection_id)

        rotated = self.setup_with_api(
            brand_id,
            TelegramSetupRequest(bot_token="9453:dedicated-worker-secret"),
            FakeTelegramApi(
                bot_id=9453,
                member_status="left",
                chats={
                    chat_id: {
                        "id": chat_id,
                        "username": "reverse_rotation_channel",
                        "title": "Reverse rotation channel",
                        "type": "channel",
                    }
                },
            ),
        )
        rotated_channel = next(source for source in rotated.sources if source.source_role == "channel")

        self.assertEqual(rotated.connection.id, initial.connection.id)
        self.assertEqual(rotated_channel.id, initial_channel.id)
        self.assertEqual(rotated_channel.bot_connection_id, rotated.connection.id)
        self.assertEqual(rotated_channel.bot_access_status, "denied")
        self.assertIsNotNone(rotated_channel.access_checked_at)
        self.assertEqual(rotated.connection.status, "reference")
        self.assertIn("channel_bot_access_denied", rotated.warnings)

    def test_connector_response_ignores_legacy_group_and_replaces_channel(self) -> None:
        brand_id = self.create_brand()
        with SessionLocal() as session:
            session.add(
                TelegramSource(
                    brand_id=brand_id,
                    username="competitor_group",
                    source_role="legacy",
                    source_kind="supergroup",
                    source_category="competitor",
                    connector_managed=False,
                    active=True,
                )
            )
            session.commit()

        first_api = FakeTelegramApi(
            bot_id=9443,
            chats={
                "@channel_a": {
                    "id": -1004403,
                    "username": "channel_a",
                    "title": "Channel A",
                    "type": "channel",
                }
            },
        )
        self.setup_with_api(
            brand_id,
            TelegramSetupRequest(
                bot_token="9443:replace-secret",
                bot_mode="polling",
                channel_ref="@channel_a",
            ),
            first_api,
        )
        second_api = FakeTelegramApi(
            bot_id=9443,
            chats={
                "@channel_b": {
                    "id": -1004404,
                    "username": "channel_b",
                    "title": "Channel B",
                    "type": "channel",
                }
            },
        )
        response = self.setup_with_api(
            brand_id,
            TelegramSetupRequest(
                bot_mode="polling",
                channel_ref="@channel_b",
            ),
            second_api,
        )

        channels = [source for source in response.sources if source.source_role == "channel"]
        self.assertEqual([source.username for source in channels], ["channel_b"])
        with SessionLocal() as session:
            old_source = session.query(TelegramSource).filter_by(brand_id=brand_id, username="channel_a").one()
            competitor = session.query(TelegramSource).filter_by(brand_id=brand_id, username="competitor_group").one()
            self.assertFalse(old_source.active)
            self.assertFalse(old_source.connector_managed)
            connector_response = telegram_setup_response(session, brand_id)
            self.assertNotIn(competitor.id, {source.id for source in connector_response.sources})

    def test_channel_only_update_does_not_downgrade_existing_polling_mode(self) -> None:
        brand_id = self.create_brand()
        self.setup_with_api(
            brand_id,
            TelegramSetupRequest(bot_token="9444:keep-polling-secret", bot_mode="polling"),
            FakeTelegramApi(bot_id=9444),
        )
        response = self.setup_with_api(
            brand_id,
            TelegramSetupRequest(channel_ref="@keep_polling_channel"),
            FakeTelegramApi(
                bot_id=9444,
                chats={
                    "@keep_polling_channel": {
                        "id": -1004405,
                        "username": "keep_polling_channel",
                        "title": "Keep polling",
                        "type": "channel",
                    }
                },
            ),
        )

        self.assertEqual(response.connection.mode, "polling")
        self.assertEqual(response.connection.status, "ready")

    def test_access_check_accepts_worker_verified_telethon_source(self) -> None:
        brand_id = self.create_brand()
        with SessionLocal() as session:
            source = TelegramSource(
                brand_id=brand_id,
                chat_id=-1004406,
                username="telethon_ready_channel",
                source_role="channel",
                source_kind="channel",
                source_category="owned",
                connector_managed=True,
                bot_access_status="unverified",
                telethon_access_status="ready",
                active=True,
            )
            session.add(source)
            session.commit()
            session.refresh(source)
            result = check_brand_telegram_source_access(source.id, session)

        self.assertTrue(result.ok)
        self.assertIn("verified_by_telethon_worker", result.issues)

    def test_access_check_uses_telethon_when_brand_bot_access_is_denied(self) -> None:
        brand_id = self.create_brand()
        chat_id = -1004412
        response = self.setup_with_api(
            brand_id,
            TelegramSetupRequest(
                bot_token="9454:telethon-fallback-secret",
                bot_mode="polling",
                channel_ref="@telethon_fallback_channel",
            ),
            FakeTelegramApi(
                bot_id=9454,
                chats={
                    "@telethon_fallback_channel": {
                        "id": chat_id,
                        "username": "telethon_fallback_channel",
                        "title": "Telethon fallback channel",
                        "type": "channel",
                    }
                },
            ),
        )
        channel = next(source for source in response.sources if source.source_role == "channel")

        with SessionLocal() as session:
            stored_channel = session.get(TelegramSource, channel.id)
            stored_channel.telethon_access_status = "ready"
            session.commit()

        denied_api = FakeTelegramApi(
            bot_id=9454,
            member_status="left",
            chats={
                chat_id: {
                    "id": chat_id,
                    "username": "telethon_fallback_channel",
                    "title": "Telethon fallback channel",
                    "type": "channel",
                }
            },
        )
        with (
            patch(
                "app.services.telegram_connector.get_settings",
                return_value=SimpleNamespace(connector_encryption_key=self.key),
            ),
            patch("app.main.TelegramBotApi", return_value=denied_api),
            SessionLocal() as session,
        ):
            result = check_brand_telegram_source_access(channel.id, session)

        self.assertTrue(result.ok)
        self.assertFalse(result.can_read_posts)
        self.assertIn("channel_bot_access_requirement_not_met", result.issues)
        self.assertIn("verified_by_telethon_worker", result.issues)
        with SessionLocal() as session:
            stored_channel = session.get(TelegramSource, channel.id)
            self.assertEqual(stored_channel.bot_access_status, "denied")
            self.assertEqual(stored_channel.telethon_access_status, "ready")

    def test_active_bot_inbox_cannot_be_deleted_and_is_required_for_capability(self) -> None:
        brand_id = self.create_brand()
        response = self.setup_with_api(
            brand_id,
            TelegramSetupRequest(bot_token="9445:protected-inbox-secret", bot_mode="polling"),
            FakeTelegramApi(bot_id=9445),
        )
        inbox = next(source for source in response.sources if source.source_role == "bot_inbox")

        with SessionLocal() as session:
            connection = session.get(TelegramBotConnection, response.connection.id)
            connection.status = "active"
            session.commit()
            active_response = telegram_setup_response(session, brand_id)
            self.assertTrue(active_response.capabilities.bot_polling)
            with self.assertRaises(HTTPException) as raised:
                delete_telegram_source(inbox.id, session)
            self.assertEqual(raised.exception.status_code, 409)
            for action in (
                lambda: update_telegram_source(inbox.id, TelegramSourceUpdate(active=False), session),
                lambda: refresh_telegram_source(inbox.id, session),
                lambda: backfill_telegram_source(
                    inbox.id,
                    TelegramSourceBackfillRequest(),
                    session,
                ),
            ):
                with self.subTest(action=action):
                    with self.assertRaises(HTTPException) as guarded:
                        action()
                    self.assertEqual(guarded.exception.status_code, 409)

            stored_inbox = session.get(TelegramSource, inbox.id)
            session.delete(stored_inbox)
            session.commit()
            missing_response = telegram_setup_response(session, brand_id)
            self.assertFalse(missing_response.capabilities.bot_polling)
            self.assertIn("bot_inbox_missing_reconnect_required", missing_response.warnings)

    def test_same_chat_and_message_are_isolated_per_brand_connection(self) -> None:
        first_brand = self.create_brand()
        second_brand = self.create_brand()
        first_response = self.setup_with_api(
            first_brand,
            TelegramSetupRequest(bot_token="9101:first-brand-secret", bot_mode="polling"),
            FakeTelegramApi(bot_id=9101, username="first_brand_bot"),
        )
        second_response = self.setup_with_api(
            second_brand,
            TelegramSetupRequest(bot_token="9102:second-brand-secret", bot_mode="polling"),
            FakeTelegramApi(bot_id=9102, username="second_brand_bot"),
        )
        update = {
            "update_id": 7,
            "message": {
                "message_id": 42,
                "date": 1_700_000_000,
                "chat": {"id": 555, "type": "private", "first_name": "Client"},
                "from": {"id": 555, "username": "client"},
                "text": "/start brand feedback",
            },
        }

        with SessionLocal() as session:
            first_connection = session.get(TelegramBotConnection, first_response.connection.id)
            ingest_connector_update(session, update, first_connection)
        with SessionLocal() as session:
            second_connection = session.get(TelegramBotConnection, second_response.connection.id)
            ingest_connector_update(session, update, second_connection)

        with SessionLocal() as session:
            mentions = (
                session.query(Mention)
                .filter(
                    Mention.brand_id.in_((first_brand, second_brand)),
                    Mention.chat_id == 555,
                    Mention.message_id == 42,
                )
                .all()
            )
            self.assertEqual({mention.brand_id for mention in mentions}, {first_brand, second_brand})
            self.assertEqual(len({mention.source_id for mention in mentions}), 2)

    def test_telethon_chat_fans_out_to_every_brand_source(self) -> None:
        first_brand = self.create_brand()
        second_brand = self.create_brand()
        chat = {"id": -100777, "username": "shared_public_channel", "type": "channel"}
        message = {
            "message_id": 77,
            "text": "Shared channel update",
            "date": datetime(2026, 7, 18, tzinfo=timezone.utc),
        }
        with SessionLocal() as session:
            first_source = TelegramSource(
                brand_id=first_brand,
                chat_id=chat["id"],
                username=chat["username"],
                source_role="channel",
                source_kind="channel",
                source_category="owned",
                monitoring_mode="all_messages",
                active=True,
            )
            second_source = TelegramSource(
                brand_id=second_brand,
                chat_id=chat["id"],
                username=chat["username"],
                source_role="channel",
                source_kind="channel",
                source_category="owned",
                monitoring_mode="all_messages",
                active=True,
            )
            session.add_all((first_source, second_source))
            session.commit()
            source_ids = [source.id for source in active_sources_for_chat(session, chat)]
            self.assertIn(first_source.id, source_ids)
            self.assertIn(second_source.id, source_ids)

        for source_id in source_ids:
            with SessionLocal() as session:
                source = session.get(TelegramSource, source_id)
                if source.brand_id not in {first_brand, second_brand}:
                    continue
                ingest_telethon_message(
                    session,
                    chat=chat,
                    message=message,
                    source_type="channel_post",
                    source_override=source,
                )

        with SessionLocal() as session:
            mentions = (
                session.query(Mention)
                .filter(
                    Mention.brand_id.in_((first_brand, second_brand)),
                    Mention.chat_id == chat["id"],
                    Mention.message_id == 77,
                )
                .all()
            )
            self.assertEqual({mention.brand_id for mention in mentions}, {first_brand, second_brand})

    def test_telethon_access_status_only_updates_connector_managed_sources(self) -> None:
        brand_id = self.create_brand()
        with SessionLocal() as session:
            managed_source = TelegramSource(
                brand_id=brand_id,
                username=f"managed_{uuid.uuid4().hex}",
                connector_managed=True,
            )
            legacy_source = TelegramSource(
                brand_id=brand_id,
                username=f"legacy_{uuid.uuid4().hex}",
                connector_managed=False,
            )
            session.add_all((managed_source, legacy_source))
            session.commit()
            managed_source_id = managed_source.id
            legacy_source_id = legacy_source.id

        set_telethon_access_status(managed_source_id, "ready")
        set_telethon_access_status(legacy_source_id, "ready")

        with SessionLocal() as session:
            managed_source = session.get(TelegramSource, managed_source_id)
            legacy_source = session.get(TelegramSource, legacy_source_id)
            self.assertEqual(managed_source.telethon_access_status, "ready")
            self.assertIsNotNone(managed_source.access_checked_at)
            self.assertEqual(legacy_source.telethon_access_status, "unverified")
            self.assertIsNone(legacy_source.access_checked_at)

        set_telethon_access_status(managed_source_id, "denied")

        with SessionLocal() as session:
            managed_source = session.get(TelegramSource, managed_source_id)
            self.assertEqual(managed_source.telethon_access_status, "denied")
            self.assertNotEqual(managed_source.telethon_access_status, "ready")
            self.assertIsNotNone(managed_source.access_checked_at)

    def test_worker_error_states_are_safe_and_retry_aware(self) -> None:
        brand_id = self.create_brand()
        response = self.setup_with_api(
            brand_id,
            TelegramSetupRequest(bot_token="9004:worker-secret", bot_mode="polling"),
            FakeTelegramApi(bot_id=9004),
        )
        connection_id = response.connection.id

        with patch(
            "app.workers.telegram_connector_worker.get_settings",
            return_value=self.settings(),
        ):
            handle_poll_error(
                connection_id,
                TelegramBotApiError("getUpdates", 429, "Too Many Requests", retry_after_seconds=19),
            )
        with SessionLocal() as session:
            connection = session.get(TelegramBotConnection, connection_id)
            self.assertEqual(connection.status, "rate_limited")
            self.assertIsNotNone(connection.retry_after_at)
            self.assertNotIn("worker-secret", connection.status_detail)

        with SessionLocal() as session:
            connection = session.get(TelegramBotConnection, connection_id)
            connection.retry_after_at = None
            session.commit()
        with patch(
            "app.workers.telegram_connector_worker.get_settings",
            return_value=self.settings(),
        ):
            handle_poll_error(connection_id, TelegramBotApiError("getUpdates", 409, "Conflict"))
        with SessionLocal() as session:
            connection = session.get(TelegramBotConnection, connection_id)
            self.assertEqual(connection.status, "conflict")
            self.assertTrue(connection.active)

        with patch(
            "app.workers.telegram_connector_worker.get_settings",
            return_value=self.settings(),
        ):
            handle_poll_error(connection_id, TelegramBotApiError("getUpdates", 401, "Unauthorized"))
        with SessionLocal() as session:
            connection = session.get(TelegramBotConnection, connection_id)
            self.assertEqual(connection.status, "invalid")
            self.assertFalse(connection.active)

    def test_worker_persists_cursor_and_does_not_execute_commands(self) -> None:
        brand_id = self.create_brand()
        response = self.setup_with_api(
            brand_id,
            TelegramSetupRequest(bot_token="9005:cursor-secret", bot_mode="polling"),
            FakeTelegramApi(bot_id=9005),
        )
        update = {
            "update_id": 55,
            "message": {
                "message_id": 8,
                "date": 1_700_000_000,
                "chat": {"id": 8080, "type": "private", "first_name": "Client"},
                "from": {"id": 8080},
                "text": "/delete @important_channel",
            },
        }
        api = MagicMock()
        api.get_updates.return_value = [update]

        with (
            patch("app.workers.telegram_connector_worker.decrypt_bot_token", return_value="unused-secret"),
            patch("app.workers.telegram_connector_worker.TelegramBotApi", return_value=api),
            patch("app.workers.telegram_connector_worker.get_settings", return_value=self.settings()),
        ):
            poll_connection(response.connection.id)

        with SessionLocal() as session:
            connection = session.get(TelegramBotConnection, response.connection.id)
            self.assertEqual(connection.last_update_id, 55)
            self.assertEqual(connection.status, "active")
            mention = session.query(Mention).filter_by(brand_id=brand_id, message_id=8).one()
            self.assertEqual(mention.text, "/delete @important_channel")
            self.assertTrue(
                session.query(TelegramSource)
                .filter_by(brand_id=brand_id, source_role="bot_inbox", active=True)
                .count()
            )
        api.get_updates.assert_called_once_with(
            offset=None,
            timeout=0,
            allowed_updates=["message", "channel_post"],
        )


class TelegramDiscussionSemanticsTests(unittest.TestCase):
    def test_discussion_group_messages_follow_collect_comments(self) -> None:
        source = SimpleNamespace(active=True, source_role="discussion", collect_posts=False, collect_comments=True)
        self.assertFalse(should_skip_source_message(source, "group_message"))
        source.collect_comments = False
        self.assertTrue(should_skip_source_message(source, "group_message"))


if __name__ == "__main__":
    unittest.main()

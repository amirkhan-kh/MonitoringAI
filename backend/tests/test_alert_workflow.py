"""The staff-group alert workflow: who reviewed it, who answered the customer, what's left.

The whole point of the buttons is accountability, so these tests pin down the parts that
would quietly destroy it: a second presser overwriting the first one's name, an "answered"
card with nobody attached, a reopened signal that instantly re-nudges, and a counter that
keeps counting closed work.
"""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from typing import Any

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.models import AlertEvent, AppState, Brand
from app.services.alert_workflow import (
    SUMMARY_STATE_KEY,
    Actor,
    actor_from_telegram_user,
    apply_alert_action,
    handle_alert_group_message,
    handle_callback_query,
    open_alert_counts,
    open_alerts_text,
    render_summary_text,
    sync_summary_message,
    today_stats,
)
from app.services.alerts import (
    bind_staff_chat,
    build_alert_keyboard,
    build_alert_text,
    deliver_one,
    due_reminder_alerts,
    get_bound_staff_chat,
    resolve_alert_chat_id,
    resolve_comment_open_url,
    send_sla_reminders,
)
from app.services.alert_workflow import handle_my_chat_member

STAFF_CHAT_ID = "-1009999999999"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FakeTelegramApi:
    """Records calls instead of hitting Telegram."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.edits: list[dict[str, Any]] = []
        self.answers: list[dict[str, Any]] = []
        self.pins: list[int] = []
        self.next_message_id = 500

    def send_message(self, chat_id, text, *, reply_markup=None, reply_to_message_id=None):
        self.next_message_id += 1
        self.sent.append(
            {
                "chat_id": chat_id,
                "text": text,
                "reply_markup": reply_markup,
                "reply_to_message_id": reply_to_message_id,
            }
        )
        return {"ok": True, "result": {"message_id": self.next_message_id, "chat": {"id": chat_id}}}

    def edit_message_text(self, chat_id, message_id, text, *, reply_markup=None):
        self.edits.append({"chat_id": chat_id, "message_id": message_id, "text": text, "reply_markup": reply_markup})
        return {"ok": True, "result": {"message_id": message_id}}

    def answer_callback_query(self, callback_query_id, text=None, *, show_alert=False):
        self.answers.append({"id": callback_query_id, "text": text, "show_alert": show_alert})
        return {"ok": True}

    def pin_chat_message(self, chat_id, message_id, *, disable_notification=True):
        self.pins.append(message_id)
        return {"ok": True}


def staff_settings(**overrides: Any):
    base = {
        "alert_telegram_chat_id": STAFF_CHAT_ID,
        "telegram_bot_token": "test-token",
        "alert_summary_enabled": False,
    }
    base.update(overrides)
    return get_settings().model_copy(update=base)


def callback_update(action: str, event_id, user: dict[str, Any], chat_id: str = STAFF_CHAT_ID) -> dict[str, Any]:
    return {
        "callback_query": {
            "id": "cb-1",
            "from": user,
            "data": f"alert:{action}:{event_id}",
            "message": {"message_id": 42, "chat": {"id": chat_id, "type": "supergroup"}},
        }
    }


class AlertWorkflowTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init_db()

    def setUp(self) -> None:
        self.brand_id = uuid.uuid4()
        with SessionLocal() as session:
            session.add(Brand(id=self.brand_id, name=f"test-brand-{self.brand_id.hex[:8]}"))
            session.commit()

    def tearDown(self) -> None:
        with SessionLocal() as session:
            session.query(AlertEvent).filter(AlertEvent.brand_id == self.brand_id).delete()
            session.query(Brand).filter(Brand.id == self.brand_id).delete()
            # Staff-bind tests write a global AppState row — clear so later cases
            # still resolve ALERT_TELEGRAM_CHAT_ID from settings.
            from app.services.alerts import STAFF_CHAT_STATE_KEY

            session.query(AppState).filter(AppState.key == STAFF_CHAT_STATE_KEY).delete()
            session.query(AppState).filter(AppState.key.like("alert_lang%")).delete()
            session.commit()

    def make_event(self, session, **overrides: Any) -> AlertEvent:
        payload = {
            "dedup_key": f"telegram:{uuid.uuid4()}",
            "platform": "telegram",
            "brand_name": "Uzum market",
            "source": "Официальный чат Uzum Market",
            "author": "Dildora",
            "text": "Buyurtmam bekor qilindi",
            "risk_level": "high",
            "risk_score": 0.8,
            "sentiment": "negative",
            "sentiment_score": -0.6,
            "summary": "Mijoz kompensatsiya kutmoqda",
            "suggested_action": "Zudlik bilan bog'laning",
            "permalink": "https://t.me/uzummarket_chat/361937",
        }
        payload.update(overrides.pop("payload", {}))
        event = AlertEvent(
            brand_id=self.brand_id,
            event_type="reputation_risk",
            status=overrides.pop("status", "sent"),
            delivery_channel="telegram",
            delivery_target=STAFF_CHAT_ID,
            payload=payload,
            sent_at=overrides.pop("sent_at", utcnow()),
            telegram_chat_id=STAFF_CHAT_ID,
            telegram_message_id=overrides.pop("telegram_message_id", 42),
            **overrides,
        )
        session.add(event)
        session.commit()
        session.refresh(event)
        return event


class OpenUrlResolutionTests(AlertWorkflowTestCase):
    def test_rebuilds_telegram_url_from_username_and_message_id(self) -> None:
        url = resolve_comment_open_url(
            {
                "platform": "telegram",
                "permalink": None,
                "chat_username": "uzummarket_chat",
                "message_id": 361937,
            },
            staff_chat_id=STAFF_CHAT_ID,
        )
        self.assertEqual(url, "https://t.me/uzummarket_chat/361937")

    def test_rebuilds_private_supergroup_url(self) -> None:
        url = resolve_comment_open_url(
            {
                "platform": "telegram",
                "chat_id": -1001866473964,
                "message_id": 42,
            },
            staff_chat_id=STAFF_CHAT_ID,
        )
        self.assertEqual(url, "https://t.me/c/1866473964/42")

    def test_rejects_staff_supports_self_link(self) -> None:
        staff_internal = STAFF_CHAT_ID[4:]
        url = resolve_comment_open_url(
            {
                "platform": "telegram",
                "permalink": f"https://t.me/c/{staff_internal}/77",
                "chat_id": int(STAFF_CHAT_ID),
                "message_id": 77,
                "source": "Supports",
            },
            staff_chat_id=STAFF_CHAT_ID,
        )
        self.assertIsNone(url)

    def test_keeps_customer_public_link(self) -> None:
        url = resolve_comment_open_url(
            {"permalink": "https://t.me/uzummarket_chat/1", "platform": "telegram"},
            staff_chat_id=STAFF_CHAT_ID,
        )
        self.assertEqual(url, "https://t.me/uzummarket_chat/1")


class CardRenderingTests(AlertWorkflowTestCase):
    def test_open_card_shows_only_reply_and_answer_buttons(self) -> None:
        with SessionLocal() as session:
            event = self.make_event(session)
            text = build_alert_text(event.payload, event)
            keyboard = build_alert_keyboard(event)

        self.assertIn("Yangi", text)
        self.assertIn("hali olinmagan", text)
        rows = keyboard["inline_keyboard"]
        # Exactly two rows: Javob berish + Javob berdim. No URL / Tekshirdim / open buttons.
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]), 1)
        self.assertEqual(len(rows[1]), 1)
        self.assertEqual(rows[0][0]["callback_data"], f"alert:reply:{event.id}")
        self.assertEqual(rows[1][0]["callback_data"], f"alert:answer:{event.id}")
        self.assertIn("Javob berish", rows[0][0]["text"])
        self.assertIn("Javob berdim", rows[1][0]["text"])
        flat = [btn for row in rows for btn in row]
        self.assertTrue(all("url" not in btn for btn in flat))
        self.assertTrue(all("alert:check:" not in btn.get("callback_data", "") for btn in flat))
        self.assertTrue(all("alert:open:" not in btn.get("callback_data", "") for btn in flat))

    def test_answered_card_names_the_support_agent_and_offers_reopen(self) -> None:
        with SessionLocal() as session:
            event = self.make_event(session)
            apply_alert_action(
                session, event, "answer", Actor(name="Aziz Karimov", user_id=7), skip_ai_verify=True
            )
            session.commit()
            text = build_alert_text(event.payload, event)
            keyboard = build_alert_keyboard(event)

        self.assertIn("Javob berildi", text)
        self.assertIn("Aziz Karimov", text)
        self.assertIn("Javob bergan xodim", text)
        self.assertEqual(keyboard["inline_keyboard"][0][0]["callback_data"], f"alert:reopen:{event.id}")

    def test_card_without_permalink_still_has_two_workflow_buttons(self) -> None:
        with SessionLocal() as session:
            event = self.make_event(session, payload={"permalink": None})
            keyboard = build_alert_keyboard(event)
        self.assertEqual(len(keyboard["inline_keyboard"]), 2)
        self.assertEqual(keyboard["inline_keyboard"][0][0]["callback_data"], f"alert:reply:{event.id}")

    def test_reply_claim_marks_in_progress_status(self) -> None:
        with SessionLocal() as session:
            event = self.make_event(session)
            changed, message = apply_alert_action(
                session, event, "reply", Actor(name="Dildora (@dildora)", user_id=1)
            )
            session.commit()
            text = build_alert_text(event.payload, event)
            keyboard = build_alert_keyboard(event)

        self.assertTrue(changed)
        self.assertEqual(event.work_status, "checked")
        self.assertIn("Tahlil qilinmoqda", text)
        self.assertIn("Dildora", text)
        self.assertNotIn("Kommentga o'tish", text)
        self.assertNotIn("boshqalar kutsin", text.lower())
        self.assertIn("Tahlil qilinmoqda", message)
        reply_btn = keyboard["inline_keyboard"][0][0]
        self.assertIn("Tahlil qilinmoqda", reply_btn["text"])
        # Claimed button becomes a platform URL so staff re-open the original comment.
        self.assertEqual(reply_btn.get("url"), "https://t.me/uzummarket_chat/361937")
        self.assertNotIn("callback_data", reply_btn)

    def test_russian_locale_buttons(self) -> None:
        with SessionLocal() as session:
            event = self.make_event(session)
            keyboard = build_alert_keyboard(event, lang="ru")
            text = build_alert_text(event.payload, event, lang="ru")
        self.assertIn("Ответить", keyboard["inline_keyboard"][0][0]["text"])
        self.assertIn("Ответил", keyboard["inline_keyboard"][1][0]["text"])
        self.assertIn("Сигнал репутационного риска", text)


class TransitionTests(AlertWorkflowTestCase):
    def test_reply_claims_card_and_same_person_can_reclaim_link(self) -> None:
        with SessionLocal() as session:
            event = self.make_event(session)
            changed, _ = apply_alert_action(session, event, "reply", Actor(name="Dildora", user_id=1))
            self.assertTrue(changed)
            self.assertEqual(event.work_status, "checked")
            self.assertEqual(event.checked_by, "Dildora")

            # Same person re-taps: keep claim (re-share deep link upstream).
            changed, message = apply_alert_action(session, event, "reply", Actor(name="Dildora", user_id=1))
            self.assertTrue(changed)
            self.assertEqual(event.work_status, "checked")
            self.assertEqual(event.checked_by, "Dildora")
            self.assertIn("Tahlil", message)

    def test_second_person_cannot_overwrite_the_first_claim(self) -> None:
        with SessionLocal() as session:
            event = self.make_event(session)
            apply_alert_action(session, event, "reply", Actor(name="Dildora", user_id=1))
            changed, message = apply_alert_action(session, event, "reply", Actor(name="Aziz", user_id=2))

        self.assertFalse(changed)
        self.assertIn("Dildora", message)
        self.assertEqual(event.checked_by, "Dildora")

    def test_legacy_check_alias_maps_to_reply_claim(self) -> None:
        with SessionLocal() as session:
            event = self.make_event(session)
            changed, _ = apply_alert_action(session, event, "check", Actor(name="Dildora", user_id=1))
            self.assertTrue(changed)
            self.assertEqual(event.work_status, "checked")

    def test_answering_with_ai_skip_credits_staff(self) -> None:
        with SessionLocal() as session:
            event = self.make_event(session)
            changed, message = apply_alert_action(
                session, event, "answer", Actor(name="Aziz", user_id=2), skip_ai_verify=True
            )

        self.assertTrue(changed)
        self.assertEqual(event.work_status, "answered")
        self.assertEqual(event.answered_by, "Aziz")
        self.assertEqual(event.checked_by, "Aziz")
        self.assertIsNotNone(event.answered_at)
        self.assertTrue((event.payload or {}).get("staff_resolution_verified"))
        self.assertIn("AI", message)

    def test_ai_verify_failure_leaves_card_unchanged(self) -> None:
        with SessionLocal() as session:
            event = self.make_event(session)
            apply_alert_action(session, event, "reply", Actor(name="Aziz", user_id=2))
            session.commit()
            with patch(
                "app.services.alert_workflow.verify_staff_resolution",
                return_value=(False, "mijoz savoli yechilmagan"),
            ):
                changed, message = apply_alert_action(
                    session, event, "answer", Actor(name="Aziz", user_id=2)
                )

        self.assertFalse(changed)
        self.assertEqual(event.work_status, "checked")
        self.assertIsNone(event.answered_by)
        self.assertIn("yetarli emas", message)

    def test_ai_verify_success_closes_and_credits(self) -> None:
        with SessionLocal() as session:
            event = self.make_event(session)
            apply_alert_action(session, event, "reply", Actor(name="Aziz", user_id=2))
            with patch(
                "app.services.alert_workflow.verify_staff_resolution",
                return_value=(True, "muammo yechilgan"),
            ):
                changed, message = apply_alert_action(
                    session, event, "answer", Actor(name="Aziz", user_id=2)
                )

        self.assertTrue(changed)
        self.assertEqual(event.work_status, "answered")
        self.assertEqual(event.answered_by, "Aziz")
        self.assertIn("tasdiqladi", message)

    def test_other_staff_cannot_close_someone_elses_claim(self) -> None:
        with SessionLocal() as session:
            event = self.make_event(session)
            apply_alert_action(session, event, "reply", Actor(name="Dildora", user_id=1))
            changed, message = apply_alert_action(
                session, event, "answer", Actor(name="Aziz", user_id=2), skip_ai_verify=True
            )

        self.assertFalse(changed)
        self.assertIn("Dildora", message)
        self.assertEqual(event.work_status, "checked")
        self.assertIsNone(event.answered_by)

    def test_answering_twice_reports_who_already_closed_it(self) -> None:
        with SessionLocal() as session:
            event = self.make_event(session)
            apply_alert_action(
                session, event, "answer", Actor(name="Aziz", user_id=2), skip_ai_verify=True
            )
            changed, message = apply_alert_action(
                session, event, "answer", Actor(name="Nodira", user_id=3), skip_ai_verify=True
            )

        self.assertFalse(changed)
        self.assertIn("Aziz", message)
        self.assertEqual(event.answered_by, "Aziz")

    def test_reopen_clears_the_answer_and_resets_the_sla_clock(self) -> None:
        with SessionLocal() as session:
            event = self.make_event(session, reminder_count=2, reminded_at=utcnow())
            apply_alert_action(
                session, event, "answer", Actor(name="Aziz", user_id=2), skip_ai_verify=True
            )
            changed, _ = apply_alert_action(session, event, "reopen", Actor(name="Nodira", user_id=3))

        self.assertTrue(changed)
        self.assertEqual(event.work_status, "open")
        self.assertIsNone(event.answered_by)
        self.assertIsNone(event.checked_by)
        self.assertEqual(event.reminder_count, 0)
        self.assertIsNone(event.reminded_at)


class ActorNameTests(unittest.TestCase):
    def test_full_name_and_username_are_both_kept(self) -> None:
        actor = actor_from_telegram_user({"id": 5, "first_name": "Aziz", "last_name": "Karimov", "username": "aziz"})
        self.assertEqual(actor.name, "Aziz Karimov (@aziz)")
        self.assertEqual(actor.user_id, 5)

    def test_username_only_account_still_gets_a_name(self) -> None:
        self.assertEqual(actor_from_telegram_user({"id": 6, "username": "support"}).name, "@support")

    def test_anonymous_account_falls_back_to_id(self) -> None:
        self.assertEqual(actor_from_telegram_user({"id": 9}).name, "id9")


class CallbackTests(AlertWorkflowTestCase):
    def test_answer_button_ai_ok_updates_row_and_rerenders(self) -> None:
        api = FakeTelegramApi()
        with SessionLocal() as session:
            event = self.make_event(session)
            event_id = event.id

        import app.services.alert_workflow as workflow

        original = workflow.get_settings
        workflow.get_settings = lambda: staff_settings()
        try:
            with patch(
                "app.services.alert_workflow.verify_staff_resolution",
                return_value=(True, "yordam yetarli"),
            ):
                with SessionLocal() as session:
                    handled = handle_callback_query(
                        api,
                        session,
                        callback_update("answer", event_id, {"id": 7, "first_name": "Aziz"}),
                    )
        finally:
            workflow.get_settings = original

        self.assertTrue(handled)
        with SessionLocal() as session:
            stored = session.get(AlertEvent, event_id)
            self.assertEqual(stored.work_status, "answered")
            self.assertEqual(stored.answered_by, "Aziz")
        self.assertEqual(len(api.edits), 1)
        self.assertIn("Aziz", api.edits[0]["text"])
        self.assertTrue(api.answers)

    def test_reply_button_claims_and_dms_comment_link(self) -> None:
        api = FakeTelegramApi()
        with SessionLocal() as session:
            event = self.make_event(session)
            event_id = event.id

        import app.services.alert_workflow as workflow

        original = workflow.get_settings
        workflow.get_settings = lambda: staff_settings()
        try:
            with SessionLocal() as session:
                handled = handle_callback_query(
                    api,
                    session,
                    callback_update("reply", event_id, {"id": 7, "first_name": "Aziz"}),
                )
        finally:
            workflow.get_settings = original

        self.assertTrue(handled)
        with SessionLocal() as session:
            stored = session.get(AlertEvent, event_id)
            self.assertEqual(stored.work_status, "checked")
            self.assertIn("Aziz", stored.checked_by or "")
        # DM to staff with a single URL button to the original platform comment.
        dm = next((m for m in api.sent if m["chat_id"] == 7), None)
        self.assertIsNotNone(dm)
        self.assertIn("Tahlil qilinmoqda", dm["text"])
        url_btn = dm["reply_markup"]["inline_keyboard"][0][0]
        self.assertEqual(url_btn["url"], "https://t.me/uzummarket_chat/361937")
        self.assertTrue(api.edits)
        self.assertIn("Tahlil qilinmoqda", api.edits[0]["text"])
        # Group card footer must not dump the link text.
        self.assertNotIn("Kommentga o'tish", api.edits[0]["text"])
        claimed_btn = api.edits[0]["reply_markup"]["inline_keyboard"][0][0]
        self.assertEqual(claimed_btn.get("url"), "https://t.me/uzummarket_chat/361937")

    def test_reply_without_permalink_still_claims_not_error(self) -> None:
        """Regression: missing deep-link must not show «ochiladigan havola yo'q» as hard fail."""
        api = FakeTelegramApi()
        with SessionLocal() as session:
            event = self.make_event(session, payload={"permalink": None})
            event_id = event.id

        import app.services.alert_workflow as workflow

        original = workflow.get_settings
        workflow.get_settings = lambda: staff_settings()
        try:
            with SessionLocal() as session:
                handled = handle_callback_query(
                    api,
                    session,
                    callback_update("reply", event_id, {"id": 7, "first_name": "Aziz"}),
                )
        finally:
            workflow.get_settings = original

        self.assertTrue(handled)
        with SessionLocal() as session:
            stored = session.get(AlertEvent, event_id)
            self.assertEqual(stored.work_status, "checked")
            self.assertIn("Aziz", stored.checked_by or "")
        self.assertTrue(api.answers)
        answer_text = api.answers[0]["text"] or ""
        self.assertIn("Tahlil qilinmoqda", answer_text)
        self.assertNotIn("ochiladigan havola yo'q", answer_text.lower())
        self.assertNotIn("no openable link", answer_text.lower())

    def test_reply_staff_self_link_still_claims(self) -> None:
        """Supports-group self-ingest link is not opened, but claim still succeeds."""
        api = FakeTelegramApi()
        with SessionLocal() as session:
            event = self.make_event(
                session,
                payload={
                    "permalink": f"https://t.me/c/{STAFF_CHAT_ID[4:]}/99",
                    "chat_id": int(STAFF_CHAT_ID),
                    "message_id": 99,
                    "source": "Supports",
                },
            )
            event_id = event.id

        import app.services.alert_workflow as workflow

        original = workflow.get_settings
        workflow.get_settings = lambda: staff_settings()
        try:
            with SessionLocal() as session:
                handled = handle_callback_query(
                    api,
                    session,
                    callback_update("reply", event_id, {"id": 7, "first_name": "Aziz"}),
                )
        finally:
            workflow.get_settings = original

        self.assertTrue(handled)
        with SessionLocal() as session:
            stored = session.get(AlertEvent, event_id)
            self.assertEqual(stored.work_status, "checked")
        answer_text = (api.answers[0]["text"] or "").lower()
        self.assertNotIn("ochiladigan havola yo'q", answer_text)
        # No DM with staff-group URL button.
        dm = next((m for m in api.sent if m["chat_id"] == 7), None)
        self.assertIsNone(dm)

    def test_second_person_reply_shows_already_claiming_not_no_link(self) -> None:
        api = FakeTelegramApi()
        with SessionLocal() as session:
            event = self.make_event(session, payload={"permalink": None})
            apply_alert_action(session, event, "reply", Actor(name="Dildora", user_id=1))
            session.commit()
            event_id = event.id

        import app.services.alert_workflow as workflow

        original = workflow.get_settings
        workflow.get_settings = lambda: staff_settings()
        try:
            with SessionLocal() as session:
                handle_callback_query(
                    api,
                    session,
                    callback_update("reply", event_id, {"id": 9, "first_name": "Aziz"}),
                )
        finally:
            workflow.get_settings = original

        answer_text = api.answers[0]["text"] or ""
        self.assertIn("Dildora", answer_text)
        self.assertNotIn("ochiladigan havola yo'q", answer_text.lower())

    def test_answer_ai_reject_does_not_credit(self) -> None:
        api = FakeTelegramApi()
        with SessionLocal() as session:
            event = self.make_event(session)
            apply_alert_action(session, event, "reply", Actor(name="Aziz", user_id=7))
            session.commit()
            event_id = event.id

        import app.services.alert_workflow as workflow

        original = workflow.get_settings
        workflow.get_settings = lambda: staff_settings()
        try:
            with patch(
                "app.services.alert_workflow.verify_staff_resolution",
                return_value=(False, "yordam yetarli emas"),
            ):
                with SessionLocal() as session:
                    handled = handle_callback_query(
                        api,
                        session,
                        callback_update("answer", event_id, {"id": 7, "first_name": "Aziz"}),
                    )
        finally:
            workflow.get_settings = original

        self.assertTrue(handled)
        with SessionLocal() as session:
            stored = session.get(AlertEvent, event_id)
            self.assertEqual(stored.work_status, "checked")
            self.assertIsNone(stored.answered_by)
        self.assertTrue(any("yetarli emas" in (a.get("text") or "") for a in api.answers))

    def test_press_from_another_chat_is_refused(self) -> None:
        api = FakeTelegramApi()
        with SessionLocal() as session:
            event = self.make_event(session)
            event_id = event.id

        import app.services.alert_workflow as workflow

        original = workflow.get_settings
        workflow.get_settings = lambda: staff_settings()
        try:
            with SessionLocal() as session:
                handled = handle_callback_query(
                    api,
                    session,
                    callback_update("answer", event_id, {"id": 7, "first_name": "Aziz"}, chat_id="-100123"),
                )
        finally:
            workflow.get_settings = original

        self.assertTrue(handled)
        self.assertEqual(api.edits, [])
        with SessionLocal() as session:
            self.assertEqual(session.get(AlertEvent, event_id).work_status, "open")
        self.assertTrue(any("xodimlar guruhida" in (a.get("text") or "") for a in api.answers))

    def test_card_chat_works_even_if_env_points_at_personal_chat(self) -> None:
        """Regression: local/dev env personal chat_id must not block Supports cards."""
        api = FakeTelegramApi()
        with SessionLocal() as session:
            event = self.make_event(session)
            event_id = event.id

        import app.services.alert_workflow as workflow

        original = workflow.get_settings
        # Wrong personal id (exactly the prod bug: 7834215608 vs Supports -100...).
        workflow.get_settings = lambda: staff_settings(alert_telegram_chat_id="7834215608")
        try:
            with SessionLocal() as session:
                handled = handle_callback_query(
                    api,
                    session,
                    callback_update("reply", event_id, {"id": 7, "first_name": "Aziz"}, chat_id=STAFF_CHAT_ID),
                )
        finally:
            workflow.get_settings = original

        self.assertTrue(handled)
        with SessionLocal() as session:
            stored = session.get(AlertEvent, event_id)
            self.assertEqual(stored.work_status, "checked")
            self.assertIn("Aziz", stored.checked_by or "")
        self.assertFalse(any("xodimlar guruhida" in (a.get("text") or "") for a in api.answers))

    def test_int_chat_id_matches_string_staff_config(self) -> None:
        api = FakeTelegramApi()
        with SessionLocal() as session:
            event = self.make_event(session)
            event_id = event.id

        import app.services.alert_workflow as workflow

        original = workflow.get_settings
        workflow.get_settings = lambda: staff_settings()
        try:
            with SessionLocal() as session:
                handled = handle_callback_query(
                    api,
                    session,
                    callback_update("reply", event_id, {"id": 9, "first_name": "Nodira"}, chat_id=int(STAFF_CHAT_ID)),
                )
        finally:
            workflow.get_settings = original

        self.assertTrue(handled)
        with SessionLocal() as session:
            self.assertEqual(session.get(AlertEvent, event_id).work_status, "checked")

    def test_unrelated_callback_is_left_for_other_handlers(self) -> None:
        with SessionLocal() as session:
            self.assertFalse(
                handle_callback_query(FakeTelegramApi(), session, {"callback_query": {"id": "x", "data": "other:1"}})
            )

    def test_group_id_command_answers_with_the_chat_id(self) -> None:
        api = FakeTelegramApi()
        with SessionLocal() as session:
            handled = handle_alert_group_message(
                api,
                session,
                {"message": {"text": "/id", "chat": {"id": -100777, "type": "supergroup", "title": "Support"}}},
            )
        self.assertTrue(handled)
        self.assertIn("-100777", api.sent[0]["text"])


class StaffGroupBindTests(AlertWorkflowTestCase):
    def test_bind_staff_chat_overrides_env_personal_chat(self) -> None:
        settings = staff_settings(alert_telegram_chat_id="7834215608")  # personal id
        with SessionLocal() as session:
            bind_staff_chat(session, -1001234567890, title="Supports", source="test")
            self.assertEqual(get_bound_staff_chat(session)["chat_id"], "-1001234567890")
            self.assertEqual(resolve_alert_chat_id(session, settings, None), "-1001234567890")

    def test_my_chat_member_admin_bind_registers_support_group(self) -> None:
        api = FakeTelegramApi()
        update = {
            "my_chat_member": {
                "chat": {"id": -100555666777, "title": "Supports", "type": "supergroup"},
                "new_chat_member": {"status": "administrator", "user": {"id": 1, "is_bot": True}},
            }
        }
        with SessionLocal() as session:
            handled = handle_my_chat_member(api, session, update)
            self.assertTrue(handled)
            self.assertEqual(get_bound_staff_chat(session)["chat_id"], "-100555666777")
        self.assertTrue(api.sent)
        self.assertIn("Support guruh ulandi", api.sent[0]["text"])

    def test_staff_command_in_group_binds_without_prior_env(self) -> None:
        api = FakeTelegramApi()
        with SessionLocal() as session:
            handled = handle_alert_group_message(
                api,
                session,
                {
                    "message": {
                        "text": "/staff",
                        "chat": {"id": -100999888777, "type": "supergroup", "title": "Supports"},
                    }
                },
            )
            self.assertTrue(handled)
            self.assertEqual(get_bound_staff_chat(session)["title"], "Supports")
        self.assertIn("Support guruh ulandi", api.sent[0]["text"])


class DeliveryTests(AlertWorkflowTestCase):
    def test_delivery_stores_the_card_location_so_buttons_can_edit_it_later(self) -> None:
        api = FakeTelegramApi()
        settings = staff_settings()
        with SessionLocal() as session:
            event = self.make_event(session, status="pending", sent_at=None, telegram_message_id=None)
            event.telegram_chat_id = None
            session.commit()

            with patch("app.services.alerts.TelegramBotApi", return_value=api):
                deliver_one(session, settings, event)
            session.refresh(event)

            self.assertEqual(event.status, "sent")
            self.assertEqual(event.telegram_message_id, 501)
            self.assertEqual(event.telegram_chat_id, STAFF_CHAT_ID)
        # First delivery already has Javob berish + Javob berdim (two rows).
        kb = api.sent[0]["reply_markup"]["inline_keyboard"]
        self.assertEqual(len(kb), 2)
        self.assertTrue(kb[0][0]["callback_data"].startswith("alert:reply:"))
        self.assertTrue(kb[1][0]["callback_data"].startswith("alert:answer:"))


class ReminderTests(AlertWorkflowTestCase):
    def test_only_overdue_unanswered_alerts_are_nudged(self) -> None:
        settings = staff_settings(alert_sla_minutes=30)
        with SessionLocal() as session:
            overdue = self.make_event(session, sent_at=utcnow() - timedelta(minutes=45))
            self.make_event(session, sent_at=utcnow() - timedelta(minutes=5))
            answered = self.make_event(session, sent_at=utcnow() - timedelta(hours=3))
            apply_alert_action(
                session, answered, "answer", Actor(name="Aziz", user_id=2), skip_ai_verify=True
            )
            session.commit()

            due = due_reminder_alerts(session, settings)
            self.assertEqual([event.id for event in due], [overdue.id])

    def test_reminders_stop_at_the_configured_cap(self) -> None:
        settings = staff_settings(alert_sla_minutes=30, alert_reminder_max=2)
        with SessionLocal() as session:
            self.make_event(session, sent_at=utcnow() - timedelta(hours=5), reminder_count=2, reminded_at=utcnow() - timedelta(hours=2))
            self.assertEqual(due_reminder_alerts(session, settings), [])

    def test_nudge_replies_to_the_card_and_counts_up(self) -> None:
        api = FakeTelegramApi()
        settings = staff_settings(alert_sla_minutes=30)
        with SessionLocal() as session:
            event = self.make_event(session, sent_at=utcnow() - timedelta(minutes=90))
            sent = send_sla_reminders(session, settings, api)
            session.refresh(event)

            self.assertEqual(sent, 1)
            self.assertEqual(event.reminder_count, 1)
            self.assertIsNotNone(event.reminded_at)
        self.assertEqual(api.sent[0]["reply_to_message_id"], 42)
        self.assertIn("javobsiz", api.sent[0]["text"])


class CounterTests(AlertWorkflowTestCase):
    def test_counter_tracks_open_work_and_drops_answered_signals(self) -> None:
        # The counter is global (one dashboard, one staff group), so assert on the delta —
        # a dev database with real signals in it must not make this test lie.
        with SessionLocal() as session:
            before = open_alert_counts(session)
            self.make_event(session)
            checked = self.make_event(session, payload={"risk_level": "critical"})
            apply_alert_action(session, checked, "reply", Actor(name="Dildora", user_id=1))
            answered = self.make_event(session)
            apply_alert_action(
                session, answered, "answer", Actor(name="Aziz", user_id=2), skip_ai_verify=True
            )
            session.commit()

            counts = open_alert_counts(session)
            stats = today_stats(session)

        self.assertEqual(counts["open"] - before["open"], 2)
        self.assertEqual(counts["checked"] - before["checked"], 1)
        self.assertEqual(counts["by_risk"].get("critical", 0) - before["by_risk"].get("critical", 0), 1)
        self.assertGreaterEqual(stats["answered"], 1)
        self.assertIn("Aziz", [row["name"] for row in stats["by_person"]])

    def test_pinned_summary_is_posted_once_then_edited_in_place(self) -> None:
        api = FakeTelegramApi()
        settings = staff_settings(alert_summary_enabled=True)
        with SessionLocal() as session:
            session.query(AppState).filter(AppState.key == SUMMARY_STATE_KEY).delete()
            session.commit()

            event = self.make_event(session)
            sync_summary_message(api, session, settings, force=True)
            self.assertEqual(len(api.sent), 1)
            self.assertEqual(api.pins, [501])

            # Unchanged board → no Telegram traffic at all. Re-store the text the renderer
            # produces *now* so the clock in "Yangilandi: HH:MM" cannot make this flaky.
            state = session.get(AppState, SUMMARY_STATE_KEY)
            state.value = {**state.value, "text": render_summary_text(session)}
            session.commit()
            sync_summary_message(api, session, settings, force=True)
            self.assertEqual(len(api.sent), 1)
            self.assertEqual(api.edits, [])

            apply_alert_action(
                session, event, "answer", Actor(name="Aziz", user_id=2), skip_ai_verify=True
            )
            session.commit()
            sync_summary_message(api, session, settings, force=True)

        self.assertEqual(len(api.sent), 1)
        self.assertEqual(len(api.edits), 1)
        self.assertEqual(api.edits[0]["message_id"], 501)

    def test_summary_and_open_list_render_source_and_link(self) -> None:
        with SessionLocal() as session:
            self.make_event(session)
            summary = render_summary_text(session)
            listing = open_alerts_text(session)

        self.assertIn("Javob kutayotgan signallar", summary)
        self.assertIn("Официальный чат Uzum Market", summary)
        self.assertIn("https://t.me/uzummarket_chat/361937", listing)


if __name__ == "__main__":
    unittest.main()

"""Staff-group workflow for reputation signals: review → reply → closed.

The bot sits in the support team's Telegram group as an admin. Every risky mention is
posted there as a card with two workflow buttons:

  🔍 Tekshirildi   — someone reviewed the AI verdict (toggle; re-press un-checks)
  💬 Javob berdim  — someone opened the link, replied to the customer, and closed it

and a deep link straight to the comment. The person's Telegram name is recorded, so the
group always shows *who* handled *what*. A pinned summary message carries the number of
signals still waiting for a reply — the "nothing is left unanswered" guarantee — and the
SLA nudges in ``alerts.send_sla_reminders`` chase whatever crosses the deadline.

State always lives in the DB (AlertEvent.work_status + who/when columns); the Telegram
message and the dashboard are two renderings of the same row, which is why a press in the
group and a click in the dashboard converge instead of fighting.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import AlertEvent, AppState
from app.services.alert_i18n import (
    DEFAULT_LANG,
    LANG_STATE_CHAT_PREFIX,
    LANG_STATE_GLOBAL,
    SUPPORTED_LANGS,
    lang_display_name,
    normalize_lang,
    t,
)
from app.services.alerts import (
    LOCAL_TZ,
    OPEN_WORK_STATUSES,
    RISK_EMOJI,
    RISK_ORDER,
    WORK_STATUS_ANSWERED,
    WORK_STATUS_CHECKED,
    WORK_STATUS_OPEN,
    bind_staff_chat,
    build_alert_keyboard,
    build_alert_text,
    duration_text,
    get_bound_staff_chat,
    get_pending_staff_invite,
    local_time_text,
    parse_telegram_chat_ref,
    resolve_alert_chat_id,
    resolve_alert_lang,
    set_pending_staff_invite,
    try_resolve_staff_chat_ref,
)
from app.services.realtime import publish_realtime_event
from app.services.telegram_api import TelegramBotApi, TelegramBotApiError

logger = logging.getLogger(__name__)

CALLBACK_NAMESPACE = "alert"
SUMMARY_STATE_KEY = "alert_summary_message"
OPEN_LIST_LIMIT = 10


def summary_keyboard(lang: str | None = None) -> dict:
    lang = lang or DEFAULT_LANG
    return {
        "inline_keyboard": [
            [
                {"text": f"🔄 {t('btn_refresh', lang)}", "callback_data": "alert:summary"},
                {"text": f"📋 {t('btn_open_list', lang)}", "callback_data": "alert:list"},
            ],
            [
                {"text": f"👥 {t('btn_staff_table', lang)}", "callback_data": "alert:leaderboard"},
                {"text": f"🌐 {t('btn_lang', lang)}", "callback_data": "alert:langmenu"},
            ],
        ]
    }


def language_keyboard(lang: str | None = None) -> dict:
    lang = lang or DEFAULT_LANG
    return {
        "inline_keyboard": [
            [
                {"text": "🇺🇿 O'zbekcha", "callback_data": "alert:setlang:uz"},
                {"text": "🇷🇺 Русский", "callback_data": "alert:setlang:ru"},
                {"text": "🇬🇧 English", "callback_data": "alert:setlang:en"},
            ]
        ]
    }


# Backward-compatible name used by older code paths / tests.
SUMMARY_KEYBOARD = summary_keyboard(DEFAULT_LANG)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


@dataclass
class Actor:
    """Whoever pressed the button — a Telegram group member or a dashboard operator."""

    name: str
    user_id: int | None = None
    source: str = "telegram"


def actor_from_telegram_user(user: dict[str, Any] | None) -> Actor:
    user = user or {}
    name = " ".join(part for part in (user.get("first_name"), user.get("last_name")) if part).strip()
    if not name and user.get("username"):
        name = f"@{user['username']}"
    if not name:
        name = f"id{user.get('id') or '?'}"
    if user.get("username") and not name.startswith("@"):
        name = f"{name} (@{user['username']})"
    user_id = user.get("id")
    return Actor(name=name[:255], user_id=int(user_id) if user_id else None)


# --------------------------------------------------------------------------- transitions


def apply_alert_action(
    session: Session,
    event: AlertEvent,
    action: str,
    actor: Actor,
    *,
    lang: str | None = None,
) -> tuple[bool, str]:
    """Apply one workflow transition. Returns ``(state_changed, message_for_actor)``.

    Two people tapping at the same moment is the normal case in a busy group, so the
    caller locks the row first and every branch here is written to be safe to lose:
    the first press wins and the second gets told who beat them to it.

    Actions:
      * ``check``  — toggle reviewed ("Tekshirdim")
      * ``open``   — claim review (tekshirilyapti) when staff opens the deep link
      * ``answer`` — mark customer replied ("Javob berdim") with staff name/username
      * ``reopen`` — undo a mistaken close
    """
    lang = lang or DEFAULT_LANG
    now = _utcnow()
    status = event.work_status or WORK_STATUS_OPEN

    if action in {"check", "open"}:
        if status == WORK_STATUS_ANSWERED:
            return False, t("toast_closed_cannot_check", lang, name=event.answered_by or "-")
        if status == WORK_STATUS_CHECKED:
            # "open" (via link) keeps the existing reviewer; "check" toggles for same person.
            if action == "open":
                return False, t(
                    "toast_already_checked_by",
                    lang,
                    name=event.checked_by or "-",
                    time=local_time_text(event.checked_at),
                )
            if event.checked_by_user_id and actor.user_id and event.checked_by_user_id != actor.user_id:
                return False, t(
                    "toast_already_checked_by",
                    lang,
                    name=event.checked_by or "-",
                    time=local_time_text(event.checked_at),
                )
            event.work_status = WORK_STATUS_OPEN
            event.checked_by = None
            event.checked_by_user_id = None
            event.checked_at = None
            return True, t("toast_check_cleared", lang)
        event.work_status = WORK_STATUS_CHECKED
        event.checked_by = actor.name
        event.checked_by_user_id = actor.user_id
        event.checked_at = now
        if action == "open":
            return True, t("toast_opening_link", lang)
        return True, t("toast_check_ok", lang)

    if action == "answer":
        if status == WORK_STATUS_ANSWERED:
            same_person = event.answered_by_user_id and actor.user_id and event.answered_by_user_id == actor.user_id
            if same_person:
                return False, t("toast_already_closed_self", lang)
            return False, t(
                "toast_already_answered_by",
                lang,
                name=event.answered_by or "-",
                time=local_time_text(event.answered_at),
            )
        event.work_status = WORK_STATUS_ANSWERED
        event.answered_by = actor.name
        event.answered_by_user_id = actor.user_id
        event.answered_at = now
        # Replying necessarily means the verdict was read, so a card can never end up
        # "answered but never checked" — which would read as a hole in the audit trail.
        if not event.checked_by:
            event.checked_by = actor.name
            event.checked_by_user_id = actor.user_id
            event.checked_at = now
        return True, t("toast_closed", lang)

    if action == "reopen":
        if status != WORK_STATUS_ANSWERED:
            return False, t("toast_already_open", lang)
        event.work_status = WORK_STATUS_CHECKED if event.checked_by else WORK_STATUS_OPEN
        event.answered_by = None
        event.answered_by_user_id = None
        event.answered_at = None
        # Give the SLA clock a fresh start instead of instantly re-nudging a reopened card.
        event.reminder_count = 0
        event.reminded_at = None
        return True, t("toast_reopened", lang, name=actor.name)

    return False, t("toast_unknown_action", lang)


def publish_alert_event(session: Session, event: AlertEvent, *, commit: bool = True) -> None:
    publish_realtime_event(
        session,
        "alert_event",
        {
            "id": event.id,
            "brand_id": event.brand_id,
            "work_status": event.work_status,
            "status": event.status,
            "checked_by": event.checked_by,
            "checked_at": event.checked_at,
            "answered_by": event.answered_by,
            "answered_at": event.answered_at,
            "payload": event.payload,
            "created_at": event.created_at,
        },
        commit=commit,
    )


def refresh_alert_card(api: TelegramBotApi, event: AlertEvent, *, lang: str | None = None) -> None:
    """Re-render the Telegram card from the row. Never raises."""
    if not event.telegram_chat_id or not event.telegram_message_id:
        return
    lang = lang or (event.payload or {}).get("lang") or DEFAULT_LANG
    try:
        api.edit_message_text(
            event.telegram_chat_id,
            event.telegram_message_id,
            build_alert_text(event.payload or {}, event, lang=lang),
            reply_markup=build_alert_keyboard(event, lang=lang),
        )
    except TelegramBotApiError as exc:
        if "not modified" not in (exc.description or "").lower():
            logger.warning("Could not refresh alert card id=%s: %s", event.id, exc)
    except Exception:  # noqa: BLE001
        logger.exception("Could not refresh alert card id=%s", event.id)


# --------------------------------------------------------------------------- callbacks


def handle_callback_query(api: TelegramBotApi, session: Session, update: dict[str, Any]) -> bool:
    """Handle an inline-button press. Returns True when the update was ours."""
    callback = update.get("callback_query")
    if not callback:
        return False
    data = str(callback.get("data") or "")
    if not data.startswith(f"{CALLBACK_NAMESPACE}:"):
        return False

    callback_id = str(callback.get("id"))
    message = callback.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    settings = get_settings()
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    lang = resolve_alert_lang(session, chat_id=str(chat_id) if chat_id is not None else None)

    if not _is_staff_chat(session, settings, chat_id):
        _safe_answer(api, callback_id, t("toast_staff_only", lang), show_alert=True)
        return True

    if action == "summary":
        sync_summary_message(api, session, settings, force=True)
        _safe_answer(api, callback_id, t("toast_refreshed", lang))
        return True
    if action == "list":
        _safe_answer(api, callback_id)
        _safe_send(api, chat_id, open_alerts_text(session, lang=lang), reply_markup=None)
        return True
    if action == "leaderboard":
        _safe_answer(api, callback_id)
        _safe_send(api, chat_id, leaderboard_text(session, lang=lang), reply_markup=None)
        return True
    if action == "langmenu":
        _safe_answer(api, callback_id)
        _safe_send(
            api,
            chat_id,
            t("lang_pick", lang) + f"\n{t('lang_help', lang, current=lang_display_name(lang))}",
            reply_markup=language_keyboard(lang),
        )
        return True
    if action == "setlang":
        next_lang = normalize_lang(parts[2] if len(parts) > 2 else DEFAULT_LANG)
        _set_chat_language(session, str(chat_id), next_lang)
        _safe_answer(api, callback_id, t("toast_lang_set", next_lang, name=lang_display_name(next_lang)))
        sync_summary_message(api, session, settings, force=True)
        return True

    # Event actions: alert:check|open|answer|reopen:<uuid>
    event_id = parts[2] if len(parts) > 2 else ""
    try:
        event_uuid = UUID(event_id)
    except (ValueError, AttributeError):
        _safe_answer(api, callback_id, t("toast_not_found", lang))
        return True

    if action == "open":
        # Deep-link claim: mark "tekshirilyapti" then guide staff to the URL button.
        actor = actor_from_telegram_user(callback.get("from"))
        try:
            event = (
                session.query(AlertEvent)
                .filter(AlertEvent.id == event_uuid)
                .with_for_update()
                .one_or_none()
            )
            if event is None:
                session.rollback()
                _safe_answer(api, callback_id, t("toast_not_found", lang))
                return True
            permalink = (event.payload or {}).get("permalink")
            if not permalink:
                session.rollback()
                _safe_answer(api, callback_id, t("toast_no_link", lang), show_alert=True)
                return True
            changed, response = apply_alert_action(session, event, "open", actor, lang=lang)
            if changed:
                publish_alert_event(session, event, commit=False)
            session.commit()
        except Exception:  # noqa: BLE001
            session.rollback()
            logger.exception("Alert open callback failed data=%s", data)
            _safe_answer(api, callback_id, t("toast_error", lang))
            return True
        _safe_answer(api, callback_id, response, show_alert=True)
        if changed:
            refresh_alert_card(api, event, lang=lang)
            sync_summary_message(api, session, settings, force=True)
        return True

    actor = actor_from_telegram_user(callback.get("from"))
    try:
        event = (
            session.query(AlertEvent)
            .filter(AlertEvent.id == event_uuid)
            .with_for_update()
            .one_or_none()
        )
        if event is None:
            session.rollback()
            _safe_answer(api, callback_id, t("toast_not_found", lang))
            return True
        changed, response = apply_alert_action(session, event, action, actor, lang=lang)
        if changed:
            publish_alert_event(session, event, commit=False)
        session.commit()
    except Exception:  # noqa: BLE001 - a failed press must not kill the poller
        session.rollback()
        logger.exception("Alert callback failed data=%s", data)
        _safe_answer(api, callback_id, t("toast_error", lang))
        return True

    _safe_answer(api, callback_id, response)
    if changed:
        refresh_alert_card(api, event, lang=lang)
        sync_summary_message(api, session, settings, force=True)
    return True


def _is_staff_chat(session: Session | None, settings: Settings, chat_id: Any) -> bool:
    """Accept bound support group, env ALERT_TELEGRAM_CHAT_ID, or brand alert_chat_id."""
    if chat_id is None:
        return False
    chat = str(chat_id).strip()
    configured = str(settings.alert_telegram_chat_id or "").strip()
    if configured and chat == configured:
        return True
    if session is None:
        return False
    try:
        bound = get_bound_staff_chat(session)
        if bound and str(bound.get("chat_id") or "").strip() == chat:
            return True
        from app.models import Brand

        for brand in session.query(Brand).filter(Brand.active.is_(True)).all():
            profile = brand.profile_config or {}
            for key in ("alert_chat_id", "support_chat_id"):
                if str(profile.get(key) or "").strip() == chat:
                    return True
    except Exception:  # noqa: BLE001
        return bool(configured) and chat == configured
    return False


def _set_chat_language(session: Session, chat_id: str, lang: str) -> None:
    lang = normalize_lang(lang)
    key = f"{LANG_STATE_CHAT_PREFIX}{chat_id}"
    value = {"lang": lang, "updated_at": _utcnow().isoformat()}
    state = session.get(AppState, key)
    if state is None:
        session.add(AppState(key=key, value=value))
    else:
        state.value = value
        state.updated_at = _utcnow()
    # Also keep a global default so new groups inherit the last choice until overridden.
    global_state = session.get(AppState, LANG_STATE_GLOBAL)
    if global_state is None:
        session.add(AppState(key=LANG_STATE_GLOBAL, value={"lang": lang}))
    else:
        global_state.value = {"lang": lang}
        global_state.updated_at = _utcnow()
    try:
        session.commit()
    except Exception:  # noqa: BLE001
        session.rollback()


def _safe_answer(api: TelegramBotApi, callback_id: str, text: str | None = None, *, show_alert: bool = False) -> None:
    try:
        api.answer_callback_query(callback_id, text, show_alert=show_alert)
    except Exception:  # noqa: BLE001
        logger.debug("answerCallbackQuery failed", exc_info=True)


def _safe_send(api: TelegramBotApi, chat_id: Any, text: str, **kwargs: Any) -> dict[str, Any] | None:
    try:
        return api.send_message(chat_id, text, **kwargs)
    except Exception:  # noqa: BLE001
        logger.debug("sendMessage failed chat=%s", chat_id, exc_info=True)
        return None


# --------------------------------------------------------------------------- group commands


def _capture_group_invite_link(api: TelegramBotApi, chat_id: int | str) -> tuple[str | None, str | None]:
    """Return (invite_link, warning). Prefer permanent export; fall back to create."""
    try:
        link = api.export_chat_invite_link(chat_id)
        if link:
            return link, None
    except Exception as exc:  # noqa: BLE001
        logger.debug("exportChatInviteLink failed chat=%s: %s", chat_id, exc)
    try:
        created = api.create_chat_invite_link(chat_id, name="MonitoringAI support")
        if created and created.get("invite_link"):
            return str(created["invite_link"]), None
    except Exception as exc:  # noqa: BLE001
        logger.debug("createChatInviteLink failed chat=%s: %s", chat_id, exc)
    return None, (
        "⚠️ Guruhda public yoki private invite link yo'q (yoki botda huquq yetarli emas).\n"
        "Telegram → Guruh sozlamalari → Invite link / Manage invite links dan link yarating.\n"
        "Keyin guruhda /staff deb yozing yoki botga private chatda linkni yuboring."
    )


def finalize_staff_group_bind(
    api: TelegramBotApi,
    session: Session,
    *,
    chat_id: int | str,
    title: str | None,
    source: str,
    chat_type: str | None = None,
    username: str | None = None,
) -> dict:
    """Bind support group, store invite link, pin summary, send status message."""
    settings = get_settings()
    invite_link, invite_warning = _capture_group_invite_link(api, chat_id)
    bound = bind_staff_chat(
        session,
        chat_id,
        title=title,
        source=source,
        invite_link=invite_link,
        username=username,
        chat_type=chat_type,
    )
    lines = [
        f"✅ Support guruh ulandi: {title or chat_id}",
        f"Chat ID: {chat_id}",
        f"Turi: {chat_type or 'group/supergroup'}",
    ]
    if invite_link:
        lines.append(f"Invite link: {invite_link}")
    if invite_warning:
        lines.append("")
        lines.append(invite_warning)
    lines.extend(
        [
            "",
            "AI tahlildan o'tgan riskli mentionlar (Telegram, YouTube, Instagram, Facebook)",
            "shu guruhga kartochka + tugmalar bilan keladi. Pin hisoblagich yoqiladi.",
            "",
            "Komandalar: /ochiq · /xodimlar · /statistika · /til · /jamlanma · /staff",
        ]
    )
    _safe_send(api, chat_id, "\n".join(lines))
    try:
        sync_summary_message(api, session, settings, force=True)
    except Exception:  # noqa: BLE001
        logger.debug("Could not pin summary after staff bind", exc_info=True)
    logger.info("Bound staff alert chat id=%s title=%s invite=%s", chat_id, title, invite_link)
    return bound


def handle_my_chat_member(api: TelegramBotApi, session: Session, update: dict[str, Any]) -> bool:
    """When the bot is added as admin to a group, bind it as the support inbox (public or private)."""
    event = update.get("my_chat_member")
    if not event:
        return False
    chat = event.get("chat") or {}
    chat_type = chat.get("type")
    # Never use channels as staff inbox.
    if chat_type not in {"group", "supergroup"}:
        return False
    new_member = event.get("new_chat_member") or {}
    status = (new_member.get("status") or "").lower()
    if status not in {"administrator", "member"}:
        return True

    chat_id = chat.get("id")
    title = chat.get("title") or "Support"
    username = chat.get("username")
    if chat_id is None:
        return True

    # Prefer admin; if only member, still bind but warn that pin/admin rights help.
    finalize_staff_group_bind(
        api,
        session,
        chat_id=chat_id,
        title=title,
        source=f"my_chat_member:{status}",
        chat_type=chat_type,
        username=username,
    )
    if status != "administrator":
        _safe_send(
            api,
            chat_id,
            "⚠️ Botni guruhda *admin* qiling (pin messages, delete messages) — "
            "pin hisoblagich va kartochka tahrirlash to'liq ishlashi uchun.",
        )
    return True


def handle_staff_private_message(api: TelegramBotApi, session: Session, update: dict[str, Any]) -> bool:
    """Private chat: /staff <invite|@username> or a bare t.me link to register support group."""
    message = update.get("message")
    if not message:
        return False
    chat = message.get("chat") or {}
    if chat.get("type") != "private":
        return False
    text = (message.get("text") or "").strip()
    if not text:
        return False
    chat_id = chat.get("id")

    command = None
    args: list[str] = []
    if text.startswith("/"):
        parts = text.split()
        command = parts[0].split("@", 1)[0].lstrip("/").lower()
        args = parts[1:]
        if command not in {"staff", "support", "guruh", "id"}:
            return False
        ref = " ".join(args).strip()
    else:
        # Bare invite / username link
        parsed = parse_telegram_chat_ref(text)
        if parsed.get("kind") not in {"invite", "username", "id"}:
            return False
        ref = text

    if not ref:
        pending = get_pending_staff_invite(session)
        bound = get_bound_staff_chat(session)
        lines = [
            "Support guruhni bog'lash:",
            "1) @monitoring_checking_bot ni Supports guruhiga qo'shing va admin qiling",
            "2) Guruhda /staff yozing",
            "yoki shu chatga guruh invite linkini yuboring (public yoki private).",
        ]
        if bound:
            lines.append(f"\nHozirgi: {bound.get('title')} · {bound.get('chat_id')}")
            if bound.get("invite_link"):
                lines.append(f"Link: {bound['invite_link']}")
        if pending:
            lines.append(f"\nKutilayotgan link: {pending.get('invite_link')}")
        _safe_send(api, chat_id, "\n".join(lines))
        return True

    resolved = try_resolve_staff_chat_ref(api, ref)
    parsed = resolved.get("parsed") or parse_telegram_chat_ref(ref)
    if resolved.get("chat") and resolved["chat"].get("id"):
        c = resolved["chat"]
        if c.get("type") == "channel":
            _safe_send(api, chat_id, "Kanal support inbox bo'la olmaydi. Guruh (group/supergroup) kerak.")
            return True
        finalize_staff_group_bind(
            api,
            session,
            chat_id=c["id"],
            title=c.get("title"),
            source="private_resolve",
            chat_type=c.get("type"),
            username=c.get("username"),
        )
        _safe_send(api, chat_id, f"Ulandi: {c.get('title')} ({c.get('id')})")
        return True

    if parsed.get("kind") == "invite":
        link = parsed.get("invite_link") or ref
        set_pending_staff_invite(session, link, note="private_chat")
        _safe_send(
            api,
            chat_id,
            (
                "Private invite saqlandi.\n"
                f"Link: {link}\n\n"
                "Botni shu guruhga qo'shib admin qiling. Qo'shilishi bilan avtomatik bog'lanadi "
                "(public yoki private farq qilmaydi).\n"
                "Agar guruhda invite link bo'lmasa — Telegram sozlamalaridan link yarating."
            ),
        )
        return True

    _safe_send(
        api,
        chat_id,
        "Link ochilmadi. Bot hali guruh a'zosi emas bo'lishi mumkin.\n"
        "1) Botni guruhga admin qilib qo'shing\n"
        "2) Guruhda /staff yozing",
    )
    return True


def handle_alert_group_message(api: TelegramBotApi, session: Session, update: dict[str, Any]) -> bool:
    """Staff-group commands: bind, list open signals, leaderboard, language, summary."""
    message = update.get("message")
    if not message:
        return False
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat.get("type") not in {"group", "supergroup"}:
        return False
    text = (message.get("text") or "").strip()
    if not text.startswith("/"):
        return False
    command = text.split()[0].split("@", 1)[0].lstrip("/").lower()
    args = text.split()[1:] if len(text.split()) > 1 else []
    settings = get_settings()
    title = chat.get("title") or "Support"

    # /id and /staff work in any group where the bot can see messages — they bind this
    # group as the destination for AI risk cards (Supports-style staff inbox).
    # Optional arg: public @username or t.me invite link for documentation / pending bind.
    if command in {"id", "staff", "support", "guruh"}:
        if args:
            ref = " ".join(args).strip()
            resolved = try_resolve_staff_chat_ref(api, ref)
            parsed = resolved.get("parsed") or {}
            if resolved.get("chat") and resolved["chat"].get("id"):
                c = resolved["chat"]
                finalize_staff_group_bind(
                    api,
                    session,
                    chat_id=c["id"],
                    title=c.get("title") or title,
                    source=f"command_{command}_resolved",
                    chat_type=c.get("type"),
                    username=c.get("username"),
                )
                return True
            if parsed.get("kind") == "invite":
                set_pending_staff_invite(session, parsed.get("invite_link") or ref, note="from_group_command")
                # Still bind the current group (bot is already here) and remember the link.
                finalize_staff_group_bind(
                    api,
                    session,
                    chat_id=chat_id,
                    title=title,
                    source=f"command_{command}_with_invite",
                    chat_type=chat.get("type"),
                    username=chat.get("username"),
                )
                return True
            if resolved.get("error"):
                _safe_send(
                    api,
                    chat_id,
                    "Linkni bot hali ocha olmadi (private invite uchun bot avval guruh a'zosi bo'lishi kerak).\n"
                    "Shu guruhni support sifatida saqlayman.",
                )
        finalize_staff_group_bind(
            api,
            session,
            chat_id=chat_id,
            title=title,
            source=f"command_{command}",
            chat_type=chat.get("type"),
            username=chat.get("username"),
        )
        return True

    if not _is_staff_chat(session, settings, chat_id):
        return False
    lang = resolve_alert_lang(session, chat_id=str(chat_id))

    if command in {"ochiq", "open"}:
        _safe_send(api, chat_id, open_alerts_text(session, lang=lang))
        return True
    if command in {"statistika", "stats", "hisobot"}:
        _safe_send(api, chat_id, stats_text(session, lang=lang))
        return True
    if command in {"jamlanma", "summary"}:
        sync_summary_message(api, session, settings, force=True)
        return True
    if command in {"xodimlar", "leaderboard", "jadval"}:
        _safe_send(api, chat_id, leaderboard_text(session, lang=lang))
        return True
    if command in {"til", "lang", "language"}:
        if args and normalize_lang(args[0]) in SUPPORTED_LANGS:
            next_lang = normalize_lang(args[0])
            _set_chat_language(session, str(chat_id), next_lang)
            _safe_send(api, chat_id, t("toast_lang_set", next_lang, name=lang_display_name(next_lang)))
            sync_summary_message(api, session, settings, force=True)
        else:
            _safe_send(
                api,
                chat_id,
                t("lang_help", lang, current=lang_display_name(lang)),
                reply_markup=language_keyboard(lang),
            )
        return True
    return False


# --------------------------------------------------------------------------- summary


def open_alert_counts(session: Session) -> dict[str, Any]:
    """Everything the pinned counter needs, in three aggregate queries."""
    risk_expr = func.lower(func.coalesce(AlertEvent.payload["risk_level"].astext, ""))
    source_expr = func.coalesce(AlertEvent.payload["source"].astext, "-")
    open_filter = (
        AlertEvent.work_status.in_(OPEN_WORK_STATUSES),
        AlertEvent.status != "abandoned",
    )

    totals = (
        session.query(
            func.count(AlertEvent.id),
            func.sum(case((AlertEvent.work_status == WORK_STATUS_CHECKED, 1), else_=0)),
            func.min(AlertEvent.created_at),
        )
        .filter(*open_filter)
        .one()
    )
    by_risk = dict(
        session.query(risk_expr, func.count(AlertEvent.id)).filter(*open_filter).group_by(risk_expr).all()
    )
    by_source = (
        session.query(source_expr, func.count(AlertEvent.id))
        .filter(*open_filter)
        .group_by(source_expr)
        .order_by(func.count(AlertEvent.id).desc())
        .limit(6)
        .all()
    )
    return {
        "open": int(totals[0] or 0),
        "checked": int(totals[1] or 0),
        "oldest_created_at": totals[2],
        "by_risk": by_risk,
        "by_source": [{"source": row[0], "count": int(row[1])} for row in by_source],
    }


def today_stats(session: Session) -> dict[str, Any]:
    start = datetime.now(LOCAL_TZ).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    answered_filter = (AlertEvent.work_status == WORK_STATUS_ANSWERED, AlertEvent.answered_at >= start)
    response_seconds = func.extract(
        "epoch", AlertEvent.answered_at - func.coalesce(AlertEvent.sent_at, AlertEvent.created_at)
    )
    row = session.query(func.count(AlertEvent.id), func.avg(response_seconds)).filter(*answered_filter).one()
    by_person = (
        session.query(AlertEvent.answered_by, func.count(AlertEvent.id))
        .filter(*answered_filter)
        .group_by(AlertEvent.answered_by)
        .order_by(func.count(AlertEvent.id).desc())
        .limit(20)
        .all()
    )
    avg_seconds = float(row[1]) if row[1] is not None else None
    return {
        "answered": int(row[0] or 0),
        "avg_response_seconds": avg_seconds,
        "by_person": [{"name": name or "-", "count": int(count)} for name, count in by_person],
    }


def render_summary_text(session: Session, *, lang: str | None = None, chat_id: str | None = None) -> str:
    lang = lang or resolve_alert_lang(session, chat_id=chat_id)
    counts = open_alert_counts(session)
    stats = today_stats(session)
    now = _utcnow()

    if counts["open"] == 0:
        header = f"✅ {t('summary_all_clear', lang)}"
    else:
        header = f"📌 {t('summary_waiting', lang, n=counts['open'])}"
    lines = [header]

    risk_bits = [
        f"{RISK_EMOJI[level]} {level} {counts['by_risk'].get(level, 0)}"
        for level in RISK_ORDER
        if counts["by_risk"].get(level)
    ]
    if risk_bits:
        lines.append(" · ".join(risk_bits))
    if counts["open"]:
        oldest = _as_utc(counts["oldest_created_at"])
        if oldest:
            lines.append(f"⏳ {t('summary_oldest', lang, d=duration_text(now - oldest))}")
        lines.append(f"👀 {t('summary_checked_waiting', lang, n=counts['checked'])}")
        lines.append("")
        lines.append(t("summary_by_source", lang))
        lines.extend(f"• {row['source']} — {row['count']}" for row in counts["by_source"])

    lines.append("")
    avg = stats["avg_response_seconds"]
    avg_text = duration_text(timedelta(seconds=avg)) if avg is not None else "-"
    lines.append(t("summary_today_closed", lang, n=stats["answered"], avg=avg_text))
    if stats["by_person"]:
        lines.append(
            t("summary_staff", lang)
            + " "
            + " · ".join(f"{row['name']} {row['count']}" for row in stats["by_person"])
        )
    lines.append(f"{t('summary_updated', lang)} {local_time_text(now)}")
    lines.append(f"🌐 {lang_display_name(lang)}")
    return "\n".join(lines)


def open_alerts_text(session: Session, limit: int = OPEN_LIST_LIMIT, *, lang: str | None = None) -> str:
    lang = lang or DEFAULT_LANG
    events = (
        session.query(AlertEvent)
        .filter(AlertEvent.work_status.in_(OPEN_WORK_STATUSES), AlertEvent.status != "abandoned")
        .order_by(AlertEvent.created_at.asc())
        .limit(limit)
        .all()
    )
    if not events:
        return f"✅ {t('open_list_empty', lang)}"

    total = (
        session.query(func.count(AlertEvent.id))
        .filter(AlertEvent.work_status.in_(OPEN_WORK_STATUSES), AlertEvent.status != "abandoned")
        .scalar()
        or 0
    )
    now = _utcnow()
    lines = [f"📋 {t('open_list_title', lang, n=total)}"]
    for index, event in enumerate(events, start=1):
        payload = event.payload or {}
        emoji = RISK_EMOJI.get((payload.get("risk_level") or "").lower(), "⚠️")
        waited = duration_text(now - (_as_utc(event.created_at) or now))
        mark = f" · 👀 {event.checked_by}" if event.work_status == WORK_STATUS_CHECKED else ""
        lines.append(f"\n{index}. {emoji} {payload.get('source') or '-'} · {waited}{mark}")
        snippet = (payload.get("text") or payload.get("summary") or "").strip().replace("\n", " ")
        if snippet:
            lines.append(f"   {snippet[:120]}")
        if payload.get("permalink"):
            lines.append(f"   {payload['permalink']}")
    if total > len(events):
        lines.append(f"\n{t('open_list_more', lang, n=total - len(events))}")
    return "\n".join(lines)


def stats_text(session: Session, *, lang: str | None = None) -> str:
    lang = lang or DEFAULT_LANG
    counts = open_alert_counts(session)
    stats = today_stats(session)
    avg = stats["avg_response_seconds"]
    lines = [
        f"📊 {t('stats_title', lang)}",
        t("stats_closed", lang, n=stats["answered"]),
        t("stats_avg", lang, avg=duration_text(timedelta(seconds=avg)) if avg is not None else "-"),
        t("stats_open", lang, open=counts["open"], checked=counts["checked"]),
    ]
    if stats["by_person"]:
        lines.append("")
        lines.append(t("summary_staff", lang))
        lines.extend(f"• {row['name']} — {row['count']}" for row in stats["by_person"])
    return "\n".join(lines)


def leaderboard_text(session: Session, *, lang: str | None = None) -> str:
    """Table of who closed how many signals today — pinned-summary companion button."""
    lang = lang or DEFAULT_LANG
    stats = today_stats(session)
    lines = [f"👥 {t('leaderboard_title', lang)}", ""]
    if not stats["by_person"]:
        lines.append(t("leaderboard_empty", lang))
        return "\n".join(lines)
    for rank, row in enumerate(stats["by_person"], start=1):
        lines.append(
            t("leaderboard_row", lang, rank=rank, name=row["name"], count=row["count"])
        )
    lines.append("")
    lines.append(t("leaderboard_total", lang, n=stats["answered"]))
    avg = stats["avg_response_seconds"]
    if avg is not None:
        lines.append(t("stats_avg", lang, avg=duration_text(timedelta(seconds=avg))))
    return "\n".join(lines)


def sync_summary_message(api: TelegramBotApi, session: Session, settings: Settings, *, force: bool = False) -> None:
    """Keep one pinned message in the group showing how much work is left. Never raises.

    Edits are skipped when the rendered text is unchanged, and otherwise throttled, so a
    busy day cannot spend the group's message-edit budget on cosmetic refreshes.
    """
    if not settings.alert_summary_enabled:
        return
    chat_id = resolve_alert_chat_id(session, settings, brand_id=None)
    if not chat_id:
        return
    chat_id = str(chat_id)
    state = session.get(AppState, SUMMARY_STATE_KEY)
    value = dict(state.value or {}) if state else {}
    same_chat = value.get("chat_id") == chat_id
    lang = resolve_alert_lang(session, chat_id=chat_id)
    keyboard = summary_keyboard(lang)

    try:
        text = render_summary_text(session, lang=lang, chat_id=chat_id)
    except Exception:  # noqa: BLE001
        logger.exception("Could not render alert summary")
        return

    if same_chat and value.get("text") == text and value.get("lang") == lang:
        return
    if not force and same_chat:
        last = value.get("updated_at")
        if last:
            try:
                age = (_utcnow() - datetime.fromisoformat(last)).total_seconds()
            except ValueError:
                age = None
            if age is not None and age < settings.alert_summary_refresh_seconds:
                return

    message_id = value.get("message_id") if same_chat else None
    if message_id:
        try:
            api.edit_message_text(chat_id, int(message_id), text, reply_markup=keyboard)
        except TelegramBotApiError as exc:
            if "not modified" in (exc.description or "").lower():
                pass
            else:
                logger.info("Pinned summary lost (%s); posting a new one", exc.description)
                message_id = None
        except Exception:  # noqa: BLE001
            logger.debug("Summary edit failed", exc_info=True)
            return

    if not message_id:
        response = _safe_send(api, chat_id, text, reply_markup=keyboard)
        if not response:
            return
        message_id = (response.get("result") or {}).get("message_id")
        if not message_id:
            return
        try:
            api.pin_chat_message(chat_id, int(message_id))
        except Exception:  # noqa: BLE001 - not being admin only costs the pin, not the counter
            logger.info("Could not pin the summary message (bot needs admin rights in the group)")

    _save_state(
        session,
        SUMMARY_STATE_KEY,
        {
            "chat_id": chat_id,
            "message_id": int(message_id),
            "text": text,
            "lang": lang,
            "updated_at": _utcnow().isoformat(),
        },
    )


def _save_state(session: Session, key: str, value: dict[str, Any]) -> None:
    try:
        state = session.get(AppState, key)
        if state is None:
            session.add(AppState(key=key, value=value))
        else:
            state.value = value
            state.updated_at = _utcnow()
        session.commit()
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.debug("Could not persist app state key=%s", key, exc_info=True)

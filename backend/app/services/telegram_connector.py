from __future__ import annotations

import base64
import hashlib
import hmac
import re
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import TelegramBotConnection, TelegramSource
from app.services.telegram_ingestion import get_message_from_update, ingest_telegram_update


class ConnectorEncryptionError(RuntimeError):
    pass


class InvalidBotLinkError(ValueError):
    pass


def _fernet(key: str | None = None) -> Fernet:
    configured_key = (key if key is not None else get_settings().connector_encryption_key).strip()
    if not configured_key:
        raise ConnectorEncryptionError("CONNECTOR_ENCRYPTION_KEY is required")
    try:
        return Fernet(configured_key.encode("ascii"))
    except (ValueError, TypeError, UnicodeEncodeError):
        raise ConnectorEncryptionError("CONNECTOR_ENCRYPTION_KEY must be a valid Fernet key") from None


def encrypt_bot_token(token: str, *, key: str | None = None) -> str:
    cleaned = token.strip()
    if not cleaned:
        raise ConnectorEncryptionError("Telegram bot token is empty")
    return _fernet(key).encrypt(cleaned.encode("utf-8")).decode("ascii")


def decrypt_bot_token(ciphertext: str, *, key: str | None = None) -> str:
    try:
        return _fernet(key).decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError, UnicodeEncodeError, UnicodeDecodeError):
        raise ConnectorEncryptionError("Telegram bot token cannot be decrypted") from None


def bot_token_fingerprint(token: str, *, key: str | None = None) -> str:
    configured_key = (key if key is not None else get_settings().connector_encryption_key).strip()
    try:
        key_bytes = base64.urlsafe_b64decode(configured_key.encode("ascii"))
    except (ValueError, TypeError, UnicodeEncodeError):
        raise ConnectorEncryptionError("CONNECTOR_ENCRYPTION_KEY must be a valid Fernet key") from None
    if len(key_bytes) != 32:
        raise ConnectorEncryptionError("CONNECTOR_ENCRYPTION_KEY must be a valid Fernet key")
    return hmac.new(key_bytes, token.strip().encode("utf-8"), hashlib.sha256).hexdigest()


def normalize_bot_username(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    cleaned = re.sub(r"^https?://", "", cleaned, flags=re.IGNORECASE)
    for prefix in ("t.me/", "telegram.me/"):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    cleaned = cleaned.split("?", 1)[0].strip("/").lstrip("@")
    if "/" in cleaned or not re.fullmatch(r"[A-Za-z0-9_]{5,32}", cleaned):
        raise InvalidBotLinkError("Telegram bot link yoki username noto'g'ri")
    return cleaned


def canonical_bot_link(username: str | None) -> str | None:
    return f"https://t.me/{username}" if username else None


def ingest_connector_update(
    session: Session,
    update: dict[str, Any],
    connection: TelegramBotConnection,
) -> Any | None:
    extracted = get_message_from_update(update)
    if not extracted:
        return None
    _, message = extracted
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    username = chat.get("username")
    chat_type = chat.get("type")

    if chat_type == "private":
        source = (
            session.query(TelegramSource)
            .filter(
                TelegramSource.brand_id == connection.brand_id,
                TelegramSource.bot_connection_id == connection.id,
                TelegramSource.source_role == "bot_inbox",
                TelegramSource.active.is_(True),
            )
            .one_or_none()
        )
    else:
        filters = []
        if chat_id is not None:
            filters.append(TelegramSource.chat_id == chat_id)
        if username:
            filters.append(TelegramSource.username == username)
        if not filters:
            return None
        source = (
            session.query(TelegramSource)
            .filter(
                TelegramSource.brand_id == connection.brand_id,
                TelegramSource.bot_connection_id == connection.id,
                TelegramSource.active.is_(True),
                or_(*filters),
            )
            .order_by(TelegramSource.created_at.asc())
            .first()
        )

    if source is None:
        return None
    return ingest_telegram_update(session, update, source_override=source)

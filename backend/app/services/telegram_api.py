from __future__ import annotations

from typing import Any

import httpx


class TelegramBotApiError(RuntimeError):
    def __init__(
        self,
        method: str,
        status_code: int,
        description: str,
        *,
        retry_after_seconds: int | None = None,
    ) -> None:
        self.method = method
        self.status_code = status_code
        self.description = description
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Telegram API {method} failed ({status_code}): {description}")


class TelegramPollingConflictError(TelegramBotApiError):
    pass


class TelegramBotApi:
    def __init__(self, token: str) -> None:
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        self._token = token
        self.base_url = f"https://api.telegram.org/bot{token}"

    def delete_webhook(self) -> dict[str, Any]:
        return self._post("deleteWebhook", {"drop_pending_updates": False})

    def get_me(self) -> dict[str, Any] | None:
        data = self._post("getMe", {})
        result = data.get("result")
        return result if isinstance(result, dict) else None

    def get_webhook_info(self) -> dict[str, Any] | None:
        data = self._post("getWebhookInfo", {})
        result = data.get("result")
        return result if isinstance(result, dict) else None

    def get_updates(
        self,
        *,
        offset: int | None,
        timeout: int,
        allowed_updates: list[str],
    ) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"timeout": timeout, "allowed_updates": allowed_updates}
        if offset is not None:
            payload["offset"] = offset
        data = self._post("getUpdates", payload, timeout=timeout + 10)
        return data.get("result", [])

    def get_chat(self, chat_id: int | str) -> dict[str, Any] | None:
        data = self._post("getChat", {"chat_id": chat_id})
        result = data.get("result")
        return result if isinstance(result, dict) else None

    def get_chat_member(self, chat_id: int | str, user_id: int) -> dict[str, Any] | None:
        data = self._post("getChatMember", {"chat_id": chat_id, "user_id": user_id})
        result = data.get("result")
        return result if isinstance(result, dict) else None

    def send_message(
        self,
        chat_id: int | str,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
        reply_to_message_id: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        if reply_to_message_id is not None:
            # The alert card may have been deleted by a staff member; a nudge must not fail then.
            payload["reply_to_message_id"] = reply_to_message_id
            payload["allow_sending_without_reply"] = True
        return self._post("sendMessage", payload)

    def edit_message_text(
        self,
        chat_id: int | str,
        message_id: int,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return self._post("editMessageText", payload)

    def answer_callback_query(
        self,
        callback_query_id: str,
        text: str | None = None,
        *,
        show_alert: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id, "show_alert": show_alert}
        if text:
            # Telegram truncates toasts at 200 chars and rejects longer ones outright.
            payload["text"] = text[:200]
        return self._post("answerCallbackQuery", payload)

    def pin_chat_message(self, chat_id: int | str, message_id: int, *, disable_notification: bool = True) -> dict[str, Any]:
        return self._post(
            "pinChatMessage",
            {"chat_id": chat_id, "message_id": message_id, "disable_notification": disable_notification},
        )

    def export_chat_invite_link(self, chat_id: int | str) -> str | None:
        data = self._post("exportChatInviteLink", {"chat_id": chat_id})
        result = data.get("result")
        return str(result) if result else None

    def create_chat_invite_link(self, chat_id: int | str, *, name: str | None = None) -> dict[str, Any] | None:
        payload: dict[str, Any] = {"chat_id": chat_id}
        if name:
            payload["name"] = name[:32]
        data = self._post("createChatInviteLink", payload)
        result = data.get("result")
        return result if isinstance(result, dict) else None

    def _post(self, method: str, payload: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(f"{self.base_url}/{method}", json=payload)
        except httpx.RequestError:
            raise TelegramBotApiError(method, 0, "network error") from None
        try:
            data = response.json()
        except ValueError:
            data = {}
        if response.status_code >= 400 or not data.get("ok"):
            error_code = int(data.get("error_code") or response.status_code)
            description = str(data.get("description") or response.reason_phrase or "unknown error")
            description = description.replace(self._token, "[REDACTED]")
            parameters = data.get("parameters") if isinstance(data.get("parameters"), dict) else {}
            retry_after = parameters.get("retry_after")
            try:
                retry_after_seconds = int(retry_after) if retry_after is not None else None
            except (TypeError, ValueError):
                retry_after_seconds = None
            error_class = TelegramPollingConflictError if method == "getUpdates" and error_code == 409 else TelegramBotApiError
            raise error_class(
                method,
                error_code,
                description,
                retry_after_seconds=retry_after_seconds,
            )
        return data

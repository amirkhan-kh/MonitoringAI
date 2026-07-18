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

    def send_message(self, chat_id: int | str, text: str) -> dict[str, Any]:
        return self._post(
            "sendMessage",
            {"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        )

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

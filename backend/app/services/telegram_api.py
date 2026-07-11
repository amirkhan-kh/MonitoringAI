from __future__ import annotations

from typing import Any

import httpx


class TelegramBotApi:
    def __init__(self, token: str) -> None:
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        self.base_url = f"https://api.telegram.org/bot{token}"

    def delete_webhook(self) -> dict[str, Any]:
        return self._post("deleteWebhook", {"drop_pending_updates": False})

    def get_me(self) -> dict[str, Any] | None:
        data = self._post("getMe", {})
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
        with httpx.Client(timeout=timeout) as client:
            response = client.post(f"{self.base_url}/{method}", json=payload)
            response.raise_for_status()
            data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API error for {method}: {data}")
        return data

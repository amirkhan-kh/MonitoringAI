from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from telethon import TelegramClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import get_settings


async def main() -> None:
    settings = get_settings()
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        raise RuntimeError("TELEGRAM_API_ID and TELEGRAM_API_HASH are required")

    client = TelegramClient(settings.telegram_session_name, settings.telegram_api_id, settings.telegram_api_hash)
    await client.connect()
    try:
        authorized = await client.is_user_authorized()
        if not authorized:
            print({"authorized": False, "session": settings.telegram_session_name})
            return
        me = await client.get_me()
        print(
            {
                "authorized": True,
                "session": settings.telegram_session_name,
                "id": getattr(me, "id", None),
                "username": getattr(me, "username", None),
                "phone": getattr(me, "phone", None),
            }
        )
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

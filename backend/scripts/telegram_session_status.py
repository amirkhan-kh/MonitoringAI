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

    session_name = sys.argv[1] if len(sys.argv) > 1 else settings.telegram_session_name
    client = TelegramClient(session_name, settings.telegram_api_id, settings.telegram_api_hash)
    result: dict[str, object]
    try:
        await client.connect()
        authorized = await client.is_user_authorized()
        if not authorized:
            result = {"authorized": False, "session": session_name}
        else:
            me = await client.get_me()
            result = {
                "authorized": True,
                "session": session_name,
                "id": getattr(me, "id", None),
                "username": getattr(me, "username", None),
            }
    except Exception as exc:
        result = {"authorized": False, "session": session_name, "error": exc.__class__.__name__}
    finally:
        try:
            await client.disconnect()
        except Exception as exc:
            result = {"authorized": False, "session": session_name, "error": exc.__class__.__name__}
    print(result)


if __name__ == "__main__":
    asyncio.run(main())

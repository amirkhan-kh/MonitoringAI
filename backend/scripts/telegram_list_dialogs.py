from __future__ import annotations

import asyncio
import sys

from telethon import TelegramClient

from app.config import get_settings


async def main() -> None:
    settings = get_settings()
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        raise RuntimeError("TELEGRAM_API_ID and TELEGRAM_API_HASH are required")

    session_name = sys.argv[1] if len(sys.argv) > 1 else settings.telegram_live_sync_session_name
    client = TelegramClient(session_name, settings.telegram_api_id, settings.telegram_api_hash)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Telethon session is not authorized")
        print("TITLE\tCHAT_ID\tUSERNAME")
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            is_channel_or_group = bool(
                getattr(entity, "broadcast", False)
                or getattr(entity, "megagroup", False)
                or entity.__class__.__name__ == "Chat"
            )
            if not is_channel_or_group:
                continue
            username = getattr(entity, "username", None)
            print(f"{dialog.name}\t{dialog.id}\t@{username}" if username else f"{dialog.name}\t{dialog.id}\t-")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

from telethon import TelegramClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import get_settings


def read_user_phone() -> str:
    raw_phone = input("Phone number (+998...): ").strip()
    phone = re.sub(r"[\s().-]", "", raw_phone)
    if ":" in phone or not re.fullmatch(r"\+?\d{7,15}", phone):
        raise RuntimeError("Enter a Telegram user phone number, not a bot token.")
    return phone


async def main() -> None:
    settings = get_settings()
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        raise RuntimeError("TELEGRAM_API_ID and TELEGRAM_API_HASH are required")

    # Optional session-name argument so a SEPARATE session can be created (e.g. an
    # independent local device login) without clobbering the main session. Creating a
    # fresh login for a distinct session name yields a distinct Telethon auth key, so
    # it can run concurrently with another machine's session (multi-device) instead of
    # conflicting the way a copied session file would.
    session_name = sys.argv[1] if len(sys.argv) > 1 else settings.telegram_session_name

    print("Telethon user login")
    print(f"Session file: {session_name}")
    print("Use your Telegram user phone number, not the bot token.")
    print("Do not share the Telegram login code in chat; type it only in this terminal.")

    client = TelegramClient(session_name, settings.telegram_api_id, settings.telegram_api_hash)
    await client.start(phone=read_user_phone)
    me = await client.get_me()
    if getattr(me, "bot", False):
        raise RuntimeError("Telethon session is authorized as a bot. Reset the session and login with a user phone number.")
    print(f"Telethon session created for: {getattr(me, 'username', None) or getattr(me, 'id', None)}")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

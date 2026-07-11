# Telegram Credential Rotation

Use this when the Telegram user account, bot, channel, or group setup changes.

## What Must Change

- `TELEGRAM_BOT_TOKEN`: new token from `@BotFather`.
- `TELEGRAM_API_ID`: API ID for the current Telegram user account.
- `TELEGRAM_API_HASH`: API hash for the current Telegram user account.
- `TELEGRAM_SESSION_NAME`: keep `.sessions/monitoring` unless a separate session is needed.
- `ALERT_TELEGRAM_CHAT_ID`: update only if alerts must go to a new chat.

## Local Rotation

Run the local helper from the project root:

```bash
python3 scripts/rotate_telegram_credentials.py
```

The helper:

- prompts for secrets in Terminal;
- validates the bot token with Telegram `getMe`;
- backs up `.env` to `.env.backup.YYYYMMDD-HHMMSS`;
- updates `.env`;
- removes old local Telethon session files;
- attempts to remove the old Docker `telegram_sessions` volume.

## After Rotation

Start Docker or Colima, then run:

```bash
make telethon-login
make telethon-status
```

The Telegram login code must be typed only in the terminal.

## Telegram Access Checklist

- Add the new bot to each channel or group used by the project.
- Make the bot admin in channels where it must read posts.
- Add the bot to linked discussion groups where it must read comments.
- Enable privacy settings appropriately in `@BotFather` if group messages must be read.
- Re-import or refresh Telegram sources from the dashboard.

## Do Not Store

- Bot tokens.
- API hashes.
- Telegram login codes.
- `.session` files.
- Service account JSON.

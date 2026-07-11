# Telegram Agent Commands

Use these commands in private chat with the monitoring bot.

## Commands

```text
/add @channel [category] [mode]
/check @channel
/sources
/backfill @channel [limit]
/pause @channel
/resume @channel
/remove @channel
/status
/help
```

Sending a Telegram source link or `@username` without a command is handled as `/add`.

## Examples

```text
/add @client_channel owned all_messages
/add @competitor_channel competitor all_messages
/add @industry_news news brand_matches_only
/check @client_channel
/backfill @client_channel 100
```

## Behavior

- `/add` resolves the source when bot access is available.
- If Bot API cannot resolve the source, it is cataloged and Telethon backfill is attempted.
- Adminless public/member channels are imported by the `telegram-live-sync` worker through the authorized Telethon user session.
- Bot admin access is still useful for Bot API channel updates and reaction-count updates, but it is not required for Telethon import when the user session can read the source.
- Linked discussion groups are added automatically when Telegram exposes them.
- New sources are attached to the first active brand by default.
- Agent commands work only in private chat with the bot.

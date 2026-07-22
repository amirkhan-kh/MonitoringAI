# MonitoringAI

Telegram-first monitoring workspace for brand source cataloging, post/comment ingestion, Gemini analysis through Vertex AI, and a dedicated dashboard UI.

Client brandning Telegram va YouTube profilini ulash bo'yicha sodda qo'llanma:
[`docs/brand-platform-ulash-qollanmasi.md`](docs/brand-platform-ulash-qollanmasi.md).

Instagram + Meta App Review ni oxirigacha yopish bo'yicha to'liq yo'l:
[`docs/instagram-meta-toliq-yol.md`](docs/instagram-meta-toliq-yol.md).

Signal inbox (xodimlar guruhi):
[`docs/signal-inbox-xodimlar-guruhi.md`](docs/signal-inbox-xodimlar-guruhi.md).

## Structure

```text
MonitoringAI/
  backend/
    app/
      models/
      services/
      workers/
    scripts/
    Dockerfile
    requirements.txt
  frontend/
    src/
      api/
      components/
      pages/
    package.json
  docker-compose.yml
  .env
```

## Running Services

- Backend API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Frontend dashboard: `http://localhost:5173`
- Postgres: `localhost:5433`

Backend services run through Docker:

```bash
docker compose up -d --build postgres api telegram-worker telegram-connector-worker telegram-live-sync youtube-worker instagram-worker facebook-worker ai-worker alert-worker
```

Frontend runs from `frontend/`:

```bash
npm install
npm run dev
```

## Telegram Monitoring Model

Each brand has a source catalog. Sources are grouped by business meaning:

- `owned`: official channels, groups, linked discussion chats.
- `bot`: client bots and bot-user interactions.
- `competitor`: competitor channels and discussions.
- `news`: media/news channels.
- `industry`: sector and market context channels.
- `influencer`: creator and expert channels.
- `community`: public chats and communities.
- `useful`: benchmark or trend sources.
- `risk`: high-risk complaint/crisis sources.
- `unknown`: unclassified sources.

Monitoring modes:

- `all_messages`: attach every post/comment from the source to the brand scope.
- `brand_matches_only`: attach only messages matching brand aliases/keywords.

### Per-brand bot connector

Each brand may save any non-empty combination of a bot reference, dedicated bot
token, channel reference, and discussion-group reference through:

- `POST /brands/{brand_id}/telegram/setup`
- `GET /brands/{brand_id}/telegram/connection`
- `DELETE /brands/{brand_id}/telegram/connection`

Before accepting bot tokens, configure one stable Fernet key in `.env`:

```bash
! grep -Eq '^CONNECTOR_ENCRYPTION_KEY=.+$' .env && \
  printf 'CONNECTOR_ENCRYPTION_KEY=%s\n' \
  "$(docker compose run --rm --no-deps api python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" >> .env
```

Important:

- Generate this key once per environment, keep it secret, back it up securely, and
  keep the same value across every API/worker restart and replica. Changing or
  losing it makes already-stored bot tokens undecryptable.
- There is no plaintext fallback. If the key is empty or invalid, token setup is
  rejected and existing encrypted tokens are not used.
- `reference` mode stores the verified bot identity but does not consume updates.
  A bot link without its token is reference-only and its inbox source stays inactive.
- `polling` is only for a dedicated/unused bot token. Telegram permits one update
  consumer per token. Setup rejects a token already used by another brand, the
  legacy global worker, or a bot with an active webhook.
- Neither worker deletes a webhook automatically. Existing production bots should
  remain in `reference` mode unless their current update transport is deliberately
  moved to this connector.
- Polling cursors persist per brand connection. `401` suspends the connection,
  `409` marks consumer conflict, and `429` honors Telegram's `retry_after` value.
- Replacing/rotating a token resets its persisted cursor. Revoke the old token with
  BotFather after the new token is verified; token revocation is not available via
  the Bot API.

Connector status values are `reference`, `legacy`, `webhook_conflict`, `ready`,
`active`, `rate_limited`, `conflict`, `invalid`, `encryption_error`, and transient `error`. API responses
return only `token_configured`; encrypted or plaintext tokens are never returned.

Recommended defaults:

```text
owned        -> all_messages
bot          -> all_messages
competitor   -> all_messages
news         -> brand_matches_only
industry     -> brand_matches_only
community    -> brand_matches_only
risk         -> all_messages
```

## Telethon Login For Full Telegram Backfill

Bot API real-time monitoring works for channels/groups where the bot has access. Historical posts, public/member competitor channels, adminless source import, post reaction snapshots, views and forwards use Telethon user access.

Current Telethon config is loaded from `.env`:

```text
TELEGRAM_API_ID=...
TELEGRAM_API_HASH=...
TELEGRAM_SESSION_NAME=.sessions/monitoring
TELEGRAM_LIVE_SYNC_SESSION_NAME=.sessions/monitoring_live
TELEGRAM_COMMAND_ALLOWED_USER_IDS=123456789
```

`TELEGRAM_COMMAND_ALLOWED_USER_IDS` accepts comma-separated Telegram user IDs or a JSON list. It is empty by default, which denies every private agent command. Add only trusted operator IDs.

The session is stored in the Docker volume mounted at `/app/.sessions`, so it remains available after containers restart.

From the project root, run:

```bash
make telethon-login
```

Create the live-sync session with a separate Telegram login/auth key:

```bash
make telethon-live-login
```

The Make target reads `TELEGRAM_LIVE_SYNC_SESSION_NAME`, stops the live worker
before opening its SQLite session, and starts the worker again when login exits.

The terminal will ask for:

```text
Phone number: +998...
Telegram login code: ...
Two-step verification password: ...   # only if enabled
```

Important:

- Use your Telegram user phone number, not the bot token.
- Enter the login code only in the terminal.
- Do not paste the Telegram login code into chat.
- Never copy a Telethon `.session` file between workers or machines. Login each session name separately; copied auth keys can be invalidated with `AuthKeyDuplicatedError`.
- The logged-in Telegram user must have access to private groups/channels that you want to backfill.
- The `telegram-live-sync` service continuously imports active public/member sources through this user session, even when the bot is not channel admin.
- If a channel has a linked discussion group, comments are imported when Telegram exposes them to the Telethon user. If not, AI analysis falls back to post text plus reaction/view/forward context.

After login, check status:

```bash
make telethon-status
make telethon-live-status
```

Successful login returns `authorized: True`. Then use the dashboard `To'liq olish`
button. CLI orqali ishlatsangiz source UUID va dashboard Bearer tokenini aniq bering:

```bash
make backfill-channel SOURCE_ID=<uuid> API_TOKEN=<bearer-token>
```

If status returns `AuthKeyDuplicatedError`, stop every process using that session, remove only the affected `.session` file, and login that session name again. Do not reuse its file on another machine.

## Source File Import Format

The frontend supports `.txt` and `.csv` import. Each line:

```text
username_or_chat_id,source_category,monitoring_mode,competitor_name,notes
```

Example:

```text
@client_channel,owned,all_messages
@client_discussion,owned,all_messages
@chec_king_bot,bot,all_messages
@competitor_channel,competitor,all_messages,Competitor A
@industry_news,news,brand_matches_only
@public_chat,community,brand_matches_only
```

## Useful API Endpoints

- `GET /health`
- `GET /events`
- `GET /brands`
- `POST /brands/{brand_id}/telegram/setup`
- `GET /brands/{brand_id}/telegram/connection`
- `DELETE /brands/{brand_id}/telegram/connection`
- `GET /telegram/bot/status`
- `GET /telegram/backfill/session-status`
- `GET /telegram/source-categories`
- `GET /telegram/sources`
- `POST /telegram/sources/access-check`
- `POST /telegram/sources/{source_id}/access-check`
- `POST /telegram/sources/import`
- `PATCH /telegram/sources/{source_id}`
- `POST /telegram/sources/{source_id}/refresh`
- `POST /telegram/sources/{source_id}/backfill`
- `GET /mentions`
- `GET /dashboard/summary`

## Realtime Updates

The dashboard uses Server-Sent Events through `GET /events`.

Flow:

```text
Telegram Bot API / Telethon -> ingestion -> Postgres NOTIFY -> API SSE -> React dashboard refresh
```

- New Telegram mentions publish `telegram_mention`.
- Gemini analysis publishes `analysis_updated`.
- Source changes publish `telegram_source`.
- The frontend debounces bursts, so a backfill or busy chat does not trigger one HTTP reload per message.
- `telegram-live-sync` uses Telethon realtime events where the authorized user receives them, plus lightweight catch-up sync for public/member sources that Telegram does not push as webhook events.

## Security

- Keep `.env` out of git.
- Keep Telegram `.session` files out of git.
- Keep Google service account JSON outside the repo.
- Regenerate any Telegram token that was exposed in chat or logs before production.

# MonitoringAI

Telegram-first monitoring workspace for brand source cataloging, post/comment ingestion, Gemini analysis through Vertex AI, and a dedicated dashboard UI.

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
docker compose up -d --build postgres api telegram-worker telegram-live-sync ai-worker
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

## Current Seeded Test Scope

The current test brand is `MonitoringChanel Test`.

Seeded Telegram sources:

```text
@monitoring_check_test  -> owned -> all_messages
MonitoringChanel Chat   -> owned -> all_messages
@chec_king_bot          -> bot   -> all_messages
Amirxon private chat    -> bot   -> all_messages
```

Access check confirms:

```text
@monitoring_check_test
bot_status: administrator
can_read_posts: true
can_read_comments: true
linked discussion: MonitoringChanel Chat
```

## Telethon Login For Full Telegram Backfill

Bot API real-time monitoring works for channels/groups where the bot has access. Historical posts, public/member competitor channels, adminless source import, post reaction snapshots, views and forwards use Telethon user access.

Current Telethon config is loaded from `.env`:

```text
TELEGRAM_API_ID=...
TELEGRAM_API_HASH=...
TELEGRAM_SESSION_NAME=.sessions/monitoring
```

The session is stored in the Docker volume mounted at `/app/.sessions`, so it remains available after containers restart.

From the project root, run:

```bash
make telethon-login
```

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
- The logged-in Telegram user must have access to private groups/channels that you want to backfill.
- The `telegram-live-sync` service continuously imports active public/member sources through this user session, even when the bot is not channel admin.
- If a channel has a linked discussion group, comments are imported when Telegram exposes them to the Telethon user. If not, AI analysis falls back to post text plus reaction/view/forward context.

After login, check status:

```bash
make telethon-status
```

Successful login returns `authorized: True`. Then use the dashboard `To'liq olish` button or run the test backfill:

```bash
make backfill-channel
```

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
- `GET /telegram/bot/status`
- `GET /telegram/backfill/session-status`
- `GET /telegram/source-categories`
- `GET /telegram/sources`
- `POST /telegram/sources/access-check`
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
# MonitoringAI

# Current Tasks

Oxirgi yangilanish: 2026-07-25

## Status snapshot

| Yo'nalish | Holat |
| --- | --- |
| Telegram monitoring + connector + live-sync | Kod tayyor (commit qilingan asos + keyingi yaxshilanishlar) |
| YouTube monitoring + quota ehtiyotkorligi | Kod tayyor |
| Instagram OAuth + webhook + poller | Kod tayyor — **Meta Console + prod env yakunlash kerak** |
| Facebook monitoring | Asosiy oqim bor; OAuth IG darajasida emas |
| Signal inbox (xodimlar workflow) | Kod tayyor — guruhda live test |
| Public Landing / Legal (Meta) | Kod tayyor |
| Source soft-delete | Kod tayyor |
| **UI AgentOS cockpit yo‘nalishi** | **Docs/skills tayyor; CSS/JSX HALI o‘zgarmagan** — qarang `design-direction-agentos-cockpit.md` |
| Docker local | **Docker Desktop ishga tushmadi** (`unable to start`) — engine tuzatilgach `compose up` |

## Next (prioritet tartibida)

### P0 — Instagram / Meta yakunlash

To'liq qadamlar: [`docs/instagram-meta-toliq-yol.md`](../instagram-meta-toliq-yol.md)

1. Meta Developer Console:
   - Valid OAuth Redirect URI: `https://monitoring.avioraai.uz/api/instagram/oauth/callback`
   - Deauthorize: `https://monitoring.avioraai.uz/api/instagram/deauthorize`
   - Data deletion callback: `https://monitoring.avioraai.uz/api/instagram/data-deletion`
   - Webhook: `https://monitoring.avioraai.uz/api/instagram/webhook` + `IG_VERIFY_TOKEN`
   - Privacy / Terms / Data deletion URL larni Basic settings ga yozish
2. Prod `.env`:
   - `APP_PUBLIC_BASE_URL=https://monitoring.avioraai.uz`
   - `IG_OAUTH_REDIRECT_URI=https://monitoring.avioraai.uz/api/instagram/oauth/callback`
   - `IG_APP_ID` / `IG_APP_SECRET` / `IG_VERIFY_TOKEN` (allaqachon borligini tasdiqlash)
3. Frontend build + API/instagram-worker restart
4. Tester IG akkaunt bilan OAuth end-to-end
5. Komment → webhook/sync → AI → (ixtiyoriy) alert
6. App Review screencast + `instagram_business_basic` + `instagram_business_manage_comments`
7. Business verification (so'ralganda)

### P0 — Signal inbox live

1. Botni xodimlar guruhiga admin qilib qo'shish
2. `ALERT_TELEGRAM_CHAT_ID` to'g'riligini tasdiqlash
3. `callback_query` allowed updates (default endi bor)
4. Test risk signal → tugmalar → dashboard `SignalInbox` sinxron
5. Docs: [`docs/signal-inbox-xodimlar-guruhi.md`](../signal-inbox-xodimlar-guruhi.md)

### P1 — Operatsion

- [x] Uncommitted ish commit (`8d5e856` — local `main`, origin dan 1 oldinda)
- [ ] `git push origin main` (ixtiyoriy, siz tasdiqlagach)
- [ ] Docker Desktop engine ni tuzatish → `docker compose up -d --build`
- [ ] Prod deploy: API image + `frontend/dist`
- [ ] Telethon session status (`make telethon-status` / live)
- [ ] Credential rotation checklist (kerak bo'lsa): `telegram-credential-rotation.md`

### Smoke (2026-07-22, Docker'siz)

- `test_instagram_oauth.py` — 15 passed
- `test_meta_api_security.py` — 8 passed
- Routes mavjud: IG oauth/webhook/deauth/data-deletion + `/alerts/*` + `/health`
- `.env`: `APP_PUBLIC_BASE_URL` va `IG_OAUTH_REDIRECT_URI` prod qiymatlari qo'shildi
- DB talab qiladigan testlar (`alert_workflow`, `source_deletion`, `youtube_quota`) Postgres host `postgres` kutadi — Docker ishlagach qayta yugurtirish

### P2 — Keyingi mahsulot

- YouTube transcript / audio AI (roadmap Level 4–5; `transcripts_supported=False`)
- Facebook OAuth / boyitilgan onboarding
- Multi-user roles (hozir bitta admin auth)
- Instagram long-lived token auto-refresh

## Done (yaqin ishlar)

- Signal inbox backend workflow (`alert_workflow.py`) + dashboard `SignalInbox`
- Alert SLA eslatma + pin summary sozlamalari
- Instagram Business Login OAuth + deauthorize/data-deletion routes
- Public Landing + Privacy/Terms/Data-deletion (auth'siz)
- Source soft-delete (Telegram/YouTube/IG/FB) + `DeleteSourceModal`
- YouTube search quota interval + overlap watermark
- Telegram connection form / BotFather guide yaxshilanishlari
- `docs/signal-inbox-xodimlar-guruhi.md`
- `docs/instagram-meta-toliq-yol.md`

## Notes

- `docs/01-planning/current-tasks.md` endi real backlog; Inbox dagi vaqtinchalik yozuvlarni shu yerga ko'chiring.
- Secretlarni notes ga yozmang.

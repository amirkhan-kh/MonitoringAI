.PHONY: up frontend-build telethon-login telethon-live-login telethon-status telethon-live-status telethon-dialogs telegram-tests backfill-channel

up:
	docker compose up -d --build postgres api telegram-worker telegram-connector-worker telegram-live-sync youtube-worker instagram-worker facebook-worker ai-worker alert-worker

frontend-build:
	cd frontend && npm run build

telethon-login:
	docker compose run --rm -it api python scripts/telegram_login.py

telethon-live-login:
	@docker compose stop telegram-live-sync >/dev/null; \
	trap 'docker compose start telegram-live-sync >/dev/null' EXIT; \
	docker compose run --rm -it api sh -lc 'python scripts/telegram_login.py "$${TELEGRAM_LIVE_SYNC_SESSION_NAME:-.sessions/monitoring_live}"'

telethon-status:
	docker compose run --rm api python scripts/telegram_session_status.py

telethon-live-status:
	@docker compose stop telegram-live-sync >/dev/null; \
	trap 'docker compose start telegram-live-sync >/dev/null' EXIT; \
	docker compose run --rm api sh -lc 'python scripts/telegram_session_status.py "$${TELEGRAM_LIVE_SYNC_SESSION_NAME:-.sessions/monitoring_live}"'

telethon-dialogs:
	@docker compose stop telegram-live-sync >/dev/null; \
	trap 'docker compose start telegram-live-sync >/dev/null' EXIT; \
	docker compose run --rm api sh -lc 'python scripts/telegram_list_dialogs.py "$${TELEGRAM_LIVE_SYNC_SESSION_NAME:-.sessions/monitoring_live}"'

telegram-tests:
	docker compose run --rm api python -m unittest discover -s tests -p 'test_telegram*.py'

backfill-channel:
	@test -n "$(SOURCE_ID)" || (echo "SOURCE_ID=<telegram-source-uuid> kerak" && exit 1)
	@test -n "$(API_TOKEN)" || (echo "API_TOKEN=<dashboard-bearer-token> kerak" && exit 1)
	curl -sS -X POST http://localhost:8000/telegram/sources/$(SOURCE_ID)/backfill \
		-H 'Authorization: Bearer $(API_TOKEN)' \
		-H 'Content-Type: application/json' \
		-d '{"limit":100,"comments_per_post":50}'

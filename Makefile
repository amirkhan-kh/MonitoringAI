.PHONY: up frontend-build telethon-login telethon-status backfill-channel

up:
	docker compose up -d --build postgres api telegram-worker ai-worker

frontend-build:
	cd frontend && npm run build

telethon-login:
	docker compose run --rm -it api python scripts/telegram_login.py

telethon-status:
	docker compose run --rm api python scripts/telegram_session_status.py

backfill-channel:
	curl -sS -X POST http://localhost:8000/telegram/sources/3e314f93-6c37-4c45-bb11-915c1cf36924/backfill \
		-H 'Content-Type: application/json' \
		-d '{"limit":100,"comments_per_post":50}'

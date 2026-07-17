#!/usr/bin/env bash
set -euo pipefail

ENV_FILE=/opt/monitoringai/.env
APP_ID=3345064788998743

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Xato: $ENV_FILE topilmadi" >&2
  exit 1
fi

read -rsp "Meta Instagram App Secretni kiriting: " APP_SECRET
echo
if [[ ${#APP_SECRET} -lt 24 ]]; then
  echo "Xato: App Secret juda qisqa. Meta dashboarddan to'liq qiymatni nusxalang." >&2
  exit 1
fi

BACKUP="${ENV_FILE}.before-meta-$(date +%Y%m%d-%H%M%S)"
cp -a "$ENV_FILE" "$BACKUP"
TMP_FILE=$(mktemp)
FOUND_ID=0
FOUND_SECRET=0

while IFS= read -r LINE || [[ -n "$LINE" ]]; do
  case "$LINE" in
    IG_APP_ID=*)
      printf "IG_APP_ID=%s\n" "$APP_ID" >> "$TMP_FILE"
      FOUND_ID=1
      ;;
    IG_APP_SECRET=*)
      printf "IG_APP_SECRET=%s\n" "$APP_SECRET" >> "$TMP_FILE"
      FOUND_SECRET=1
      ;;
    *)
      printf "%s\n" "$LINE" >> "$TMP_FILE"
      ;;
  esac
done < "$ENV_FILE"

[[ $FOUND_ID -eq 1 ]] || printf "IG_APP_ID=%s\n" "$APP_ID" >> "$TMP_FILE"
[[ $FOUND_SECRET -eq 1 ]] || printf "IG_APP_SECRET=%s\n" "$APP_SECRET" >> "$TMP_FILE"
chmod --reference="$ENV_FILE" "$TMP_FILE"
chown --reference="$ENV_FILE" "$TMP_FILE"
mv "$TMP_FILE" "$ENV_FILE"
unset APP_SECRET

cd /opt/monitoringai
docker compose -f docker-compose.prod.yml up -d --force-recreate api instagram-worker
sleep 4
curl -fsS http://127.0.0.1:18090/health >/dev/null
echo "Tayyor: yangi Meta App ID va App Secret serverga saqlandi."
echo "Backup: $BACKUP"

#!/bin/zsh
cd "$(dirname "$0")" || exit 1
python3 scripts/rotate_telegram_credentials.py
status=$?
echo
echo "Done with exit code: $status"
echo "Press Enter to close this window."
read
exit "$status"

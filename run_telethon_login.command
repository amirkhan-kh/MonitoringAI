#!/bin/zsh
cd "$(dirname "$0")" || exit 1

echo "Telethon login for MonitoringAI"
echo
echo "Use your Telegram user phone number, not the bot token."
echo "Type the Telegram login code only in this Terminal window."
echo

make telethon-login
status=$?

echo
if [ "$status" -eq 0 ]; then
  echo "Checking Telethon session status..."
  make telethon-status
else
  echo "Telethon login failed or was cancelled."
fi

echo
echo "Done with exit code: $status"
echo "Press Enter to close this window."
read
exit "$status"

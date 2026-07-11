#!/bin/zsh
cd "$(dirname "$0")/frontend" || exit 1

echo "Starting MonitoringAI frontend"
echo "URL: http://localhost:5173"
echo

npm run dev

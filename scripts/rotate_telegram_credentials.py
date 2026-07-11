#!/usr/bin/env python3
from __future__ import annotations

import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
ENV_EXAMPLE_PATH = ROOT / ".env.example"
DEFAULT_SESSION_NAME = ".sessions/monitoring"


def prompt_value(label: str, *, required: bool = True, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{label}{suffix}: ").strip()
        if value:
            return value
        if default is not None:
            return default
        if not required:
            return ""
        print("Required value.")


def prompt_secret(label: str, *, required: bool = True) -> str:
    while True:
        value = getpass.getpass(f"{label}: ").strip()
        if value or not required:
            return value
        print("Required value.")


def prompt_yes_no(label: str, *, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    value = input(f"{label} [{suffix}]: ").strip().lower()
    if not value:
        return default
    return value in {"y", "yes", "ha", "h"}


def env_value(value: str) -> str:
    if "\n" in value or "\r" in value:
        raise ValueError("Environment values cannot contain newlines.")
    return value


def read_env_lines() -> list[str]:
    if ENV_PATH.exists():
        return ENV_PATH.read_text(encoding="utf-8").splitlines(keepends=True)
    if ENV_EXAMPLE_PATH.exists():
        return ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines(keepends=True)
    return []


def update_env_lines(lines: list[str], updates: dict[str, str]) -> list[str]:
    pattern = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=")
    seen: set[str] = set()
    result: list[str] = []

    for line in lines:
        match = pattern.match(line)
        if match and match.group(1) in updates:
            key = match.group(1)
            newline = "\n" if line.endswith("\n") else ""
            result.append(f"{key}={env_value(updates[key])}{newline}")
            seen.add(key)
        else:
            result.append(line)

    missing = [key for key in updates if key not in seen]
    if missing and result and not result[-1].endswith("\n"):
        result[-1] += "\n"
    for key in missing:
        result.append(f"{key}={env_value(updates[key])}\n")

    return result


def backup_env() -> Path | None:
    if not ENV_PATH.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = ENV_PATH.with_name(f".env.backup.{timestamp}")
    shutil.copy2(ENV_PATH, backup_path)
    os.chmod(backup_path, 0o600)
    return backup_path


def validate_api_id(value: str) -> str:
    if not value.isdigit():
        raise ValueError("TELEGRAM_API_ID must be numeric.")
    return value


def validate_bot_token(token: str) -> bool:
    request = urllib.request.Request(f"https://api.telegram.org/bot{token}/getMe", method="POST")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"Bot token check failed: Telegram returned HTTP {exc.code}.")
        return False
    except Exception as exc:
        print(f"Bot token check skipped/failed: {exc}")
        return False

    if not data.get("ok"):
        print("Bot token check failed: Telegram did not accept this token.")
        return False

    result = data.get("result") or {}
    username = result.get("username")
    bot_id = result.get("id")
    print(f"Bot token OK. Bot: @{username}" if username else f"Bot token OK. Bot id: {bot_id}")
    return True


def run(command: list[str]) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    except FileNotFoundError:
        return 127, f"Command not found: {command[0]}"
    return completed.returncode, completed.stdout.strip()


def reset_local_session_files(session_name: str) -> list[Path]:
    removed: list[Path] = []
    candidates = {
        ROOT / f"{session_name}.session",
        ROOT / f"{session_name}.session-journal",
        ROOT / "backend" / f"{session_name}.session",
        ROOT / "backend" / f"{session_name}.session-journal",
    }

    for path in sorted(candidates):
        if path.exists():
            path.unlink()
            removed.append(path)
    return removed


def reset_docker_session_volume() -> None:
    code, output = run(["docker", "volume", "ls", "--format", "{{.Name}}"])
    if code != 0:
        print("Docker volume reset skipped.")
        if output:
            print(output)
        return

    volumes = output.splitlines()
    expected = "monitoringai_telegram_sessions"
    candidates = [name for name in volumes if name == expected]
    if not candidates:
        candidates = [name for name in volumes if name.endswith("_telegram_sessions")]

    if not candidates:
        print("No telegram_sessions Docker volume found.")
        return

    run(["docker", "compose", "down"])
    for volume in candidates:
        code, output = run(["docker", "volume", "rm", volume])
        if code == 0:
            print(f"Removed Docker volume: {volume}")
        else:
            print(f"Could not remove Docker volume {volume}: {output}")


def main() -> int:
    print("Telegram credential rotation for MonitoringAI")
    print("Paste secrets here in Terminal only, not in chat.")
    print()

    bot_token = prompt_secret("New TELEGRAM_BOT_TOKEN from @BotFather")
    if not validate_bot_token(bot_token):
        if not prompt_yes_no("Continue and write this token anyway?", default=False):
            return 1

    api_id = validate_api_id(prompt_value("New TELEGRAM_API_ID"))
    api_hash = prompt_secret("New TELEGRAM_API_HASH")
    session_name = prompt_value("TELEGRAM_SESSION_NAME", default=DEFAULT_SESSION_NAME)
    alert_chat_id = prompt_value("ALERT_TELEGRAM_CHAT_ID, blank if not used", required=False)

    updates = {
        "TELEGRAM_BOT_TOKEN": bot_token,
        "TELEGRAM_API_ID": api_id,
        "TELEGRAM_API_HASH": api_hash,
        "TELEGRAM_SESSION_NAME": session_name,
        "ALERT_TELEGRAM_CHAT_ID": alert_chat_id,
    }

    backup_path = backup_env()
    new_lines = update_env_lines(read_env_lines(), updates)
    ENV_PATH.write_text("".join(new_lines), encoding="utf-8")
    os.chmod(ENV_PATH, 0o600)

    print()
    if backup_path:
        print(f"Backup created: {backup_path}")
    print(f"Updated: {ENV_PATH}")

    removed = reset_local_session_files(session_name)
    if removed:
        for path in removed:
            print(f"Removed local session file: {path}")

    if prompt_yes_no("Reset old Docker Telethon session volume?", default=True):
        reset_docker_session_volume()

    print()
    print("Next steps:")
    print("1. Start Docker/Colima if it is not running.")
    print("2. Run: make telethon-login")
    print("3. Run: make telethon-status")
    print("4. Add the new bot as admin/member in the Telegram channels and linked discussion groups.")
    print("5. In the dashboard, refresh or re-import Telegram sources.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.")
        raise SystemExit(130)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)

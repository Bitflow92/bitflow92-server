#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = BASE_DIR / "firmware_dashboard"
STATUS_FILE = DASHBOARD_DIR / "status.json"
HISTORY_DIR = DASHBOARD_DIR / "history"

DASHBOARD_DIR.mkdir(exist_ok=True)
HISTORY_DIR.mkdir(exist_ok=True)

def default_status():
    return {
        "status": "idle",
        "phase": "Waiting for requirement",
        "progress": 0,
        "updated_at": "",
        "requirement": "",
        "validation_token": "",
        "attempt": 0,
        "max_attempts": 3,
        "code_review": "",
        "board_status": "",
        "terminal_output": "",
        "terminal_outputs": [],
        "result": "",
        "commit_url": "",
        "logs": []
    }

def load_status():
    if STATUS_FILE.exists():
        try:
            return {**default_status(), **json.loads(STATUS_FILE.read_text())}
        except Exception:
            pass

    return default_status()

def rebuild_terminal_output(status):
    terminal_outputs = status.get("terminal_outputs", [])
    if not isinstance(terminal_outputs, list):
        terminal_outputs = []

    parts = []
    for entry in terminal_outputs:
        if not isinstance(entry, dict):
            continue

        time_value = entry.get("time", "")
        content = entry.get("content", "")
        if not content:
            continue

        parts.append(
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{time_value}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{content}"
        )

    status["terminal_outputs"] = terminal_outputs[-50:]
    status["terminal_output"] = "\n\n".join(parts[-50:])

def save_status(status):
    status["updated_at"] = datetime.now(timezone.utc).isoformat()
    STATUS_FILE.write_text(json.dumps(status, indent=2))

def main():
    if len(sys.argv) < 2:
        print("Usage: update_dashboard.py '<json>'")
        sys.exit(1)

    update = json.loads(sys.argv[1])
    status = load_status()

    log_message = update.pop("log", None)
    terminal_output = update.pop("terminal_output", None)

    status.update(update)

    # If a new workflow clears logs, also clear terminal output history.
    if "logs" in update and update.get("logs") == []:
        status["terminal_outputs"] = []
        status["terminal_output"] = ""

    if log_message:
        logs = status.get("logs", [])
        if not isinstance(logs, list):
            logs = []

        logs.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "message": log_message
        })
        status["logs"] = logs[-100:]

    if terminal_output:
        terminal_outputs = status.get("terminal_outputs", [])
        if not isinstance(terminal_outputs, list):
            terminal_outputs = []

        terminal_outputs.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "content": str(terminal_output)
        })

        status["terminal_outputs"] = terminal_outputs[-50:]
        rebuild_terminal_output(status)

    save_status(status)

    if status.get("result") in ["PASS", "FAIL"]:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        history_file = HISTORY_DIR / f"{timestamp}_{status.get('result')}.json"
        history_file.write_text(json.dumps(status, indent=2))

if __name__ == "__main__":
    main()

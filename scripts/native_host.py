"""Chrome Native Messaging bridge for the local HR Agent launcher."""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LAUNCHER_SCRIPT = PROJECT_ROOT / "scripts" / "launcher.py"
LAUNCHER_HEALTH_URL = "http://127.0.0.1:17890/health"
MAX_MESSAGE_BYTES = 1_048_576


def _launcher_running() -> bool:
    try:
        with urllib.request.urlopen(LAUNCHER_HEALTH_URL, timeout=1) as response:
            if response.status != 200:
                return False
            return bool(json.loads(response.read().decode("utf-8")).get("launcher"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return False


def ensure_launcher() -> dict:
    if _launcher_running():
        return {"ok": True, "status": "already_running"}

    creationflags = 0
    if sys.platform == "win32":
        creationflags = (
            subprocess.CREATE_NO_WINDOW
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP
        )

    subprocess.Popen(
        [sys.executable, str(LAUNCHER_SCRIPT)],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )

    for _ in range(8):
        time.sleep(0.25)
        if _launcher_running():
            return {"ok": True, "status": "started"}
    return {"ok": False, "error": "The local launcher could not be started."}


def _read_message() -> dict:
    raw_length = sys.stdin.buffer.read(4)
    if len(raw_length) != 4:
        raise ValueError("Missing native message length.")
    message_length = int.from_bytes(raw_length, byteorder=sys.byteorder)
    if message_length > MAX_MESSAGE_BYTES:
        raise ValueError("Native message is too large.")
    raw_message = sys.stdin.buffer.read(message_length)
    if len(raw_message) != message_length:
        raise ValueError("Incomplete native message.")
    message = json.loads(raw_message.decode("utf-8"))
    if not isinstance(message, dict):
        raise ValueError("Native message must be an object.")
    return message


def _write_message(message: dict) -> None:
    payload = json.dumps(message, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(len(payload).to_bytes(4, byteorder=sys.byteorder))
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


def main() -> None:
    try:
        message = _read_message()
        if message.get("action") != "ensure_launcher":
            _write_message({"ok": False, "error": "Unsupported native action."})
            return
        _write_message(ensure_launcher())
    except Exception as exc:
        _write_message({"ok": False, "error": str(exc)})


if __name__ == "__main__":
    main()

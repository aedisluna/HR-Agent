"""Lightweight local launcher for the HR Agent backend.

Run once per Windows session:
    python scripts/launcher.py

The browser extension can then start the FastAPI backend via:
    POST http://127.0.0.1:17890/start-backend
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import APP_VERSION
from app.logging_setup import append_launcher_log
BACKEND_PORT = 8001
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
BACKEND_HEALTH_URL = f"{BACKEND_URL}/health"
LAUNCHER_PORT = 17890
BACKEND_PROCESS: subprocess.Popen | None = None
LAUNCHER_CLIENT_HEADER = "X-HR-Agent-Client"
LAUNCHER_CLIENT_VALUE = "extension"
_ALLOWED_ORIGIN_PREFIXES = ("chrome-extension://", "moz-extension://")


def api_version_compatible(reported: str | None) -> bool:
    if not reported:
        return True
    reported_parts = reported.split(".")
    expected_parts = APP_VERSION.split(".")
    return reported_parts[:2] == expected_parts[:2]


def _read_health() -> dict | None:
    try:
        with urllib.request.urlopen(BACKEND_HEALTH_URL, timeout=2) as response:
            if response.status != 200:
                return None
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None


def backend_running() -> bool:
    health = _read_health()
    if not health:
        return False
    version = health.get("version")
    return api_version_compatible(version)


def start_backend() -> dict:
    global BACKEND_PROCESS

    if backend_running():
        append_launcher_log(f"Backend already running at {BACKEND_URL}")
        return {"status": "already_running", "url": BACKEND_URL}

    if BACKEND_PROCESS and BACKEND_PROCESS.poll() is None:
        BACKEND_PROCESS.terminate()
        BACKEND_PROCESS = None

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW

    BACKEND_PROCESS = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(BACKEND_PORT),
        ],
        cwd=PROJECT_ROOT,
        creationflags=creationflags,
    )
    append_launcher_log(
        f"Started backend pid={BACKEND_PROCESS.pid} on {BACKEND_URL}"
    )
    return {"status": "started", "url": BACKEND_URL, "pid": BACKEND_PROCESS.pid}


def _pids_on_port(port: int) -> list[int]:
    if sys.platform == "win32":
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            check=False,
        )
        pids: set[int] = set()
        for line in result.stdout.splitlines():
            if f":{port}" not in line or "LISTENING" not in line:
                continue
            parts = line.split()
            if not parts:
                continue
            try:
                pids.add(int(parts[-1]))
            except ValueError:
                continue
        return sorted(pids)

    result = subprocess.run(
        ["lsof", "-ti", f":{port}"],
        capture_output=True,
        text=True,
        check=False,
    )
    pids = []
    for line in result.stdout.splitlines():
        try:
            pids.append(int(line.strip()))
        except ValueError:
            continue
    return pids


def _terminate_pid(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/PID", str(pid)],
            capture_output=True,
            check=False,
        )
        return
    subprocess.run(["kill", "-9", str(pid)], capture_output=True, check=False)


def stop_backend() -> dict:
    global BACKEND_PROCESS

    stopped: list[int] = []

    if BACKEND_PROCESS and BACKEND_PROCESS.poll() is None:
        BACKEND_PROCESS.terminate()
        try:
            BACKEND_PROCESS.wait(timeout=5)
        except subprocess.TimeoutExpired:
            BACKEND_PROCESS.kill()
        stopped.append(BACKEND_PROCESS.pid)
        BACKEND_PROCESS = None

    for pid in _pids_on_port(BACKEND_PORT):
        if pid in stopped:
            continue
        _terminate_pid(pid)
        stopped.append(pid)

    if backend_running():
        append_launcher_log("Stop backend requested, but backend still responds")
        return {
            "status": "still_running",
            "url": BACKEND_URL,
            "stopped_pids": stopped,
        }

    append_launcher_log(f"Stopped backend pids={stopped or 'none'}")
    return {
        "status": "stopped",
        "url": BACKEND_URL,
        "stopped_pids": stopped,
    }


class LauncherHandler(BaseHTTPRequestHandler):
    def _allowed_cors_origin(self) -> str | None:
        origin = self.headers.get("Origin")
        if not origin:
            return None
        if origin.startswith(_ALLOWED_ORIGIN_PREFIXES):
            return origin
        return None

    def _launcher_client_ok(self) -> bool:
        return self.headers.get(LAUNCHER_CLIENT_HEADER) == LAUNCHER_CLIENT_VALUE

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        origin = self._allowed_cors_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            f"Content-Type, {LAUNCHER_CLIENT_HEADER}",
        )
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self._send(204, {})

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, {"status": "ok", "launcher": True})
            return

        if self.path == "/backend-status":
            self._send(
                200,
                {
                    "backend_running": backend_running(),
                    "url": BACKEND_URL,
                },
            )
            return

        self._send(404, {"error": "not_found"})

    def do_POST(self) -> None:
        if not self._launcher_client_ok():
            self._send(403, {"error": "forbidden"})
            return

        if self.path == "/start-backend":
            try:
                append_launcher_log("Start backend requested by extension")
                result = start_backend()
                self._send(200, result)
            except Exception as exc:
                append_launcher_log(f"Start backend failed: {exc}")
                self._send(500, {"error": str(exc)})
            return

        if self.path == "/stop-backend":
            try:
                append_launcher_log("Stop backend requested by extension")
                result = stop_backend()
                self._send(200, result)
            except Exception as exc:
                append_launcher_log(f"Stop backend failed: {exc}")
                self._send(500, {"error": str(exc)})
            return

        self._send(404, {"error": "not_found"})

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    append_launcher_log(f"Launcher started on port {LAUNCHER_PORT}")
    server = HTTPServer(("127.0.0.1", LAUNCHER_PORT), LauncherHandler)
    print(f"HR Agent launcher on http://127.0.0.1:{LAUNCHER_PORT}")
    print("Press Ctrl+C to stop the launcher.")
    server.serve_forever()


if __name__ == "__main__":
    main()

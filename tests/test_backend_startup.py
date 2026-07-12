import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from app.config import APP_VERSION


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict | None = None,
    timeout: float = 5,
) -> dict:
    request = urllib.request.Request(url, method=method, headers=headers or {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


@unittest.skipUnless(os.name == "nt", "Windows launcher integration test")
class BackendStartupIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.backend_port = _free_port()
        self.launcher_port = _free_port()
        self.backend_url = f"http://127.0.0.1:{self.backend_port}"
        self.launcher_url = f"http://127.0.0.1:{self.launcher_port}"
        self.backend_owned = False
        env = os.environ.copy()
        env.update(
            {
                "HR_AGENT_BACKEND_PORT": str(self.backend_port),
                "HR_AGENT_LAUNCHER_PORT": str(self.launcher_port),
                "HR_AGENT_DATA_DIR": str(Path(self.temp_dir.name) / "data"),
                "HR_AGENT_LOGS_DIR": str(Path(self.temp_dir.name) / "logs"),
            }
        )
        self.launcher = subprocess.Popen(
            [sys.executable, "scripts/launcher.py"],
            cwd=PROJECT_ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def tearDown(self):
        if self.backend_owned:
            try:
                _request_json(
                    f"{self.launcher_url}/stop-backend",
                    method="POST",
                    headers={"X-HR-Agent-Client": "extension"},
                )
            except (urllib.error.URLError, TimeoutError):
                pass
        if self.launcher.poll() is None:
            self.launcher.terminate()
            try:
                self.launcher.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.launcher.kill()
                self.launcher.wait(timeout=5)
        self.temp_dir.cleanup()

    def _wait_for_json(self, url: str) -> dict:
        last_error = None
        for _ in range(30):
            try:
                return _request_json(url)
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
                time.sleep(0.2)
        self.fail(f"Timed out waiting for {url}: {last_error}")

    def test_launcher_starts_backend_and_health_then_stops_it(self):
        launcher_health = self._wait_for_json(f"{self.launcher_url}/health")
        self.assertEqual(launcher_health, {"status": "ok", "launcher": True})

        started = _request_json(
            f"{self.launcher_url}/start-backend",
            method="POST",
            headers={"X-HR-Agent-Client": "extension"},
        )
        self.assertEqual(started["status"], "started")

        backend_health = self._wait_for_json(f"{self.backend_url}/health")
        self.assertEqual(backend_health, {"status": "ok", "version": APP_VERSION})
        self.backend_owned = True

        stopped = _request_json(
            f"{self.launcher_url}/stop-backend",
            method="POST",
            headers={"X-HR-Agent-Client": "extension"},
        )
        self.assertEqual(stopped["status"], "stopped")
        self.backend_owned = False

        with self.assertRaises(urllib.error.URLError):
            _request_json(f"{self.backend_url}/health")


if __name__ == "__main__":
    unittest.main()
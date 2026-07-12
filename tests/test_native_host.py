import json
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import native_host


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class NativeHostTests(unittest.TestCase):
    def test_native_manifest_allows_only_the_pinned_extension(self):
        manifest = json.loads(
            (PROJECT_ROOT / "scripts" / "native_host_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["name"], "com.hr_agent.launcher")
        self.assertEqual(manifest["path"], "native_host.bat")
        self.assertEqual(
            manifest["allowed_origins"],
            ["chrome-extension://jdbpgjkoggegaojkeaijkcjnopnkjfoa/"],
        )

    def test_native_host_uses_python_311_when_no_virtualenv_exists(self):
        launcher = (PROJECT_ROOT / "scripts" / "native_host.bat").read_text(
            encoding="utf-8"
        )

        self.assertRegex(launcher, r"(?m)^\s*py -3\.11 ")
        self.assertNotIn('py -3 "%~dp0native_host.py"', launcher)

    def test_ensure_launcher_does_not_spawn_duplicate(self):
        with patch("scripts.native_host._launcher_running", return_value=True), patch(
            "scripts.native_host.subprocess.Popen"
        ) as popen:
            result = native_host.ensure_launcher()

        self.assertEqual(result, {"ok": True, "status": "already_running"})
        popen.assert_not_called()

    def test_ensure_launcher_starts_detached_process(self):
        with patch(
            "scripts.native_host._launcher_running", side_effect=[False, True]
        ), patch("scripts.native_host.time.sleep"), patch(
            "scripts.native_host.subprocess.Popen"
        ) as popen:
            result = native_host.ensure_launcher()

        self.assertEqual(result, {"ok": True, "status": "started"})
        popen.assert_called_once()


if __name__ == "__main__":
    unittest.main()

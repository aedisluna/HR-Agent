import unittest
from unittest.mock import Mock, patch

from scripts import launcher


class LauncherRuntimeTests(unittest.TestCase):
    @patch("scripts.launcher.subprocess.Popen")
    @patch("scripts.launcher.backend_running", return_value=False)
    @patch("scripts.launcher.find_spec")
    def test_missing_runtime_dependency_returns_actionable_error(
        self,
        find_spec_mock,
        _backend_running,
        popen,
    ):
        find_spec_mock.side_effect = lambda name: None if name == "uvicorn" else object()

        result = launcher.start_backend()

        self.assertEqual(result["status"], "runtime_error")
        self.assertIn("uvicorn", result["error"])
        popen.assert_not_called()

    @patch("scripts.launcher.subprocess.Popen")
    @patch("scripts.launcher.backend_running", return_value=False)
    @patch("scripts.launcher.find_spec", return_value=object())
    def test_ready_runtime_starts_backend_with_current_interpreter(
        self,
        _find_spec,
        _backend_running,
        popen,
    ):
        process = Mock(pid=12345)
        popen.return_value = process

        result = launcher.start_backend()

        self.assertEqual(
            result,
            {"status": "started", "url": launcher.BACKEND_URL, "pid": 12345},
        )
        self.assertEqual(popen.call_args.args[0][0], launcher.sys.executable)


if __name__ == "__main__":
    unittest.main()
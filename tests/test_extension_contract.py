import json
import re
import unittest
from pathlib import Path

from app.config import APP_VERSION


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ExtensionVersionContractTests(unittest.TestCase):
    def test_extension_and_backend_versions_are_compatible(self):
        manifest = json.loads(
            (PROJECT_ROOT / "extension" / "manifest.json").read_text(encoding="utf-8")
        )
        backend_js = (
            PROJECT_ROOT / "extension" / "lib" / "backend.js"
        ).read_text(encoding="utf-8")

        match = re.search(
            r'EXPECTED_API_MAJOR_MINOR\s*=\s*"([0-9]+\.[0-9]+)"',
            backend_js,
        )
        self.assertIsNotNone(match)

        api_major_minor = ".".join(APP_VERSION.split(".")[:2])
        self.assertEqual(manifest["version"], APP_VERSION)
        self.assertEqual(match.group(1), api_major_minor)


if __name__ == "__main__":
    unittest.main()

"""Small static baseline checks that do not access scanners, SMB, or private data."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReleaseStaticChecks(unittest.TestCase):
    def test_required_files(self):
        for rel in (
            "VERSION", "README.md", "SECURITY.md", ".gitignore",
            "web/app.py", "web/static/index.html", "web/static/app.js",
            "scan_batch.sh", "finalize.sh", "ocr_progress.py",
        ):
            self.assertTrue((ROOT / rel).exists(), rel)

    def test_no_insecure_session_fallback(self):
        app = (ROOT / "web/app.py").read_text(encoding="utf-8")
        self.assertIn('len(SECRET) < 32', app)
        self.assertIn('https_only=HTTPS_ONLY', app)

    def test_scanner_specifics_are_environment_driven(self):
        scan = (ROOT / "scan_batch.sh").read_text(encoding="utf-8")
        self.assertIn("SCANSERVER_SANE_DEVICE", scan)
        self.assertIn("SCANSERVER_SCANNER_STATUS_URL", scan)
        import re
        self.assertIsNone(re.search(r"\b192\.168\.\d{1,3}\.\d{1,3}\b", scan))

    def test_legacy_proxy_module_not_shipped(self):
        self.assertFalse((ROOT / "web/security.py").exists())

    def test_version_matches_changelog(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"[{version}]", log)


if __name__ == "__main__":
    unittest.main()

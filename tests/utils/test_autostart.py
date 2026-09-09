"""Unit tests for macOS LaunchAgents autostart manager."""

import plistlib
import tempfile
import unittest
from pathlib import Path

from src.utils.autostart import disable_autostart, enable_autostart, is_autostart_enabled


class TestAutostart(unittest.TestCase):
    def test_enable_and_disable_autostart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            plist_path = Path(tmp_dir) / "com.test.ghbotmac.plist"

            self.assertFalse(is_autostart_enabled(plist_path))

            app_root = Path(tmp_dir) / "app"
            success = enable_autostart(app_root=app_root, plist_path=plist_path)
            self.assertTrue(success)
            self.assertTrue(plist_path.exists())
            self.assertTrue(is_autostart_enabled(plist_path))

            with open(plist_path, "rb") as f:
                data = plistlib.load(f)
            self.assertEqual(data["Label"], "com.mateohdz.ghbotmac")
            self.assertTrue(data["RunAtLoad"])
            self.assertIn("--background", data["ProgramArguments"])

            disable_success = disable_autostart(plist_path)
            self.assertTrue(disable_success)
            self.assertFalse(plist_path.exists())
            self.assertFalse(is_autostart_enabled(plist_path))


if __name__ == "__main__":
    unittest.main()

"""Unit tests for Pre-Commit SecretScanner and engine integration."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from src.config.manager import ConfigManager
from src.config.models import AppConfig, ProjectConfig, ProjectMode
from src.core.engine import BotEngine
from src.core.state import SyncStatus
from src.git.secret_scanner import SecretScanner


class TestSecretScanner(unittest.TestCase):
    def setUp(self) -> None:
        self.scanner = SecretScanner()

    def test_detect_github_pat(self) -> None:
        content = "TOKEN=ghp_123456789012345678901234567890123456"
        matches = self.scanner.scan_content(content)
        self.assertEqual(len(matches), 1)
        self.assertIn("GitHub Personal Access Token", matches[0].rule_name)
        self.assertEqual(matches[0].redacted_preview, "ghp...456")

    def test_detect_aws_key(self) -> None:
        content = "export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
        matches = self.scanner.scan_content(content)
        self.assertEqual(len(matches), 1)
        self.assertIn("AWS Access Key", matches[0].rule_name)

    def test_detect_private_key(self) -> None:
        content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...\n-----END RSA PRIVATE KEY-----"
        matches = self.scanner.scan_content(content)
        self.assertEqual(len(matches), 1)
        self.assertIn("Private Cryptographic Key", matches[0].rule_name)

    def test_ignore_safe_placeholders(self) -> None:
        content = "API_KEY=your_api_key\nTOKEN=placeholder"
        matches = self.scanner.scan_content(content)
        self.assertEqual(len(matches), 0)

    def test_scan_diff_added_lines_only(self) -> None:
        diff_text = (
            "--- a/config.py\n"
            "+++ b/config.py\n"
            "@@ -1,3 +1,3 @@\n"
            "-OLD_KEY=ghp_111111111111111111111111111111111111\n"
            "+NEW_KEY=ghp_222222222222222222222222222222222222\n"
            " SAFE_LINE=test\n"
        )
        matches = self.scanner.scan_diff(diff_text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].file_path, "config.py")

    def test_excluded_paths_ignored_in_diff(self) -> None:
        diff_text = (
            "--- a/tests/test_api.py\n"
            "+++ b/tests/test_api.py\n"
            "@@ -0,0 +1,2 @@\n"
            "+TOKEN = 'ghp_123456789012345678901234567890123456'\n"
            "+KEY = 'AKIAIOSFODNN7EXAMPLE'\n"
        )
        matches = self.scanner.scan_diff(diff_text)
        self.assertEqual(len(matches), 0)


class TestEngineSecretBlocking(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.repo_dir = self.root / "secret_repo"
        self.repo_dir.mkdir()

        subprocess.run(["git", "init", str(self.repo_dir)], check=True, capture_output=True)

        init_file = self.repo_dir / "init.txt"
        init_file.write_text("clean initial content")
        subprocess.run(["git", "-C", str(self.repo_dir), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.repo_dir), "commit", "-m", "init"], check=True, capture_output=True)

        self.config_path = self.root / "config.json"
        self.config_manager = ConfigManager(self.config_path)

        self.project = ProjectConfig(
            name="SecretBlockProj",
            path=self.repo_dir,
            mode=ProjectMode.COMMIT_ONLY,
            enabled=True,
            debounce_seconds=300,
        )
        app_config = AppConfig(projects=[self.project])
        self.config_manager.save_config(app_config)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_engine_aborts_commit_when_secret_detected(self) -> None:
        engine = BotEngine(config_manager=self.config_manager)
        engine.start()

        leaked_file = self.repo_dir / "credentials.py"
        leaked_file.write_text("GITHUB_TOKEN = 'ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890'\n")

        success = engine.process_project_sync(self.project, manual=False)
        self.assertFalse(success)

        state = engine.get_project_state("SecretBlockProj")
        self.assertIsNotNone(state)
        self.assertEqual(state.last_sync_status, SyncStatus.COMMIT_FAILED)
        self.assertEqual(state.last_error_type, "SECRET_DETECTED")
        self.assertIn("credenciales", state.last_error or "")

        last_commit = engine.git_manager.get_last_commit_info(self.repo_dir)
        self.assertIsNotNone(last_commit)
        self.assertEqual(last_commit.message, "init")

        engine.stop()


if __name__ == "__main__":
    unittest.main()

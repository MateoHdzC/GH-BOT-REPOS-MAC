"""Unit tests for configuration manager and models."""

import json
import tempfile
import unittest
from pathlib import Path

from src.config.manager import ConfigManager
from src.config.models import AppConfig, ProjectConfig


class TestConfigManager(unittest.TestCase):
    def test_load_nonexistent_config_returns_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            nonexistent = Path(tmp_dir) / "does_not_exist.json"
            manager = ConfigManager(nonexistent)
            config = manager.load_config()

            self.assertIsInstance(config, AppConfig)
            self.assertEqual(len(config.projects), 0)

    def test_load_valid_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            config_file = tmp_path / "projects.json"
            data = {
                "default_debounce_seconds": 120,
                "projects": [
                    {
                        "name": "ProjectA",
                        "path": str(tmp_path / "repo_a"),
                        "enabled": True,
                        "remote": "origin",
                        "branch": "main",
                        "commit_message": "custom commit",
                        "debounce_seconds": 60,
                    },
                    {
                        "name": "ProjectB",
                        "path": str(tmp_path / "repo_b"),
                        "enabled": False,
                    },
                ],
            }
            config_file.write_text(json.dumps(data), encoding="utf-8")

            manager = ConfigManager(config_file)
            config = manager.load_config()

            self.assertEqual(config.default_debounce_seconds, 120)
            self.assertEqual(len(config.projects), 2)

            p_a = config.projects[0]
            self.assertEqual(p_a.name, "ProjectA")
            self.assertTrue(p_a.enabled)
            self.assertEqual(p_a.commit_message, "custom commit")
            self.assertEqual(p_a.debounce_seconds, 60)

            p_b = config.projects[1]
            self.assertEqual(p_b.name, "ProjectB")
            self.assertFalse(p_b.enabled)
            self.assertEqual(p_b.debounce_seconds, 120)

            enabled = config.get_enabled_projects()
            self.assertEqual(len(enabled), 1)
            self.assertEqual(enabled[0].name, "ProjectA")

    def test_load_malformed_json_graceful(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            config_file = tmp_path / "bad.json"
            config_file.write_text("{ broken json content ...", encoding="utf-8")

            manager = ConfigManager(config_file)
            config = manager.load_config()

            self.assertIsInstance(config, AppConfig)
            self.assertEqual(len(config.projects), 0)

    def test_save_and_reload_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            config_file = tmp_path / "saved_projects.json"
            manager = ConfigManager(config_file)

            original_config = AppConfig(
                projects=[
                    ProjectConfig(
                        name="TestProject",
                        path=tmp_path / "test_repo",
                        enabled=True,
                        commit_message="test: save",
                        debounce_seconds=45,
                    )
                ],
                default_debounce_seconds=150,
            )

            success = manager.save_config(original_config)
            self.assertTrue(success)
            self.assertTrue(config_file.exists())

            reloaded = manager.load_config()
            self.assertEqual(reloaded.default_debounce_seconds, 150)
            self.assertEqual(len(reloaded.projects), 1)
            self.assertEqual(reloaded.projects[0].name, "TestProject")
            self.assertEqual(reloaded.projects[0].commit_message, "test: save")
            self.assertEqual(reloaded.projects[0].debounce_seconds, 45)


if __name__ == "__main__":
    unittest.main()

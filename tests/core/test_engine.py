"""Integration tests for the BotEngine coordinator."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from src.config.models import ProjectConfig
from src.core.engine import BotEngine


class TestBotEngine(unittest.TestCase):
    def _create_git_repo(self, path: Path) -> None:
        subprocess.run(["git", "init", "-b", "main"], cwd=str(path), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Bot Test"], cwd=str(path), check=True)
        subprocess.run(["git", "config", "user.email", "bot@test.local"], cwd=str(path), check=True)

    def test_engine_sync_pipeline_creates_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            local_repo = tmp_path / "engine_repo"
            local_repo.mkdir()
            self._create_git_repo(local_repo)

            config_file = tmp_path / "config.json"
            project_cfg = ProjectConfig(
                name="EngineTest",
                path=local_repo,
                enabled=True,
                commit_message="auto: test commit from engine",
                debounce_seconds=1,
            )
            config_file.write_text(
                json.dumps({
                    "default_debounce_seconds": 1,
                    "projects": [{
                        "name": project_cfg.name,
                        "path": str(project_cfg.path),
                        "enabled": True,
                        "commit_message": project_cfg.commit_message,
                        "debounce_seconds": 1,
                    }],
                }),
                encoding="utf-8",
            )

            engine = BotEngine(config_path=config_file)
            engine.start()

            new_file = local_repo / "feature.txt"
            new_file.write_text("Engine test content\n", encoding="utf-8")

            success = engine.process_project_sync(project_cfg)
            self.assertTrue(success)

            log_check = subprocess.run(
                ["git", "log", "-1", "--pretty=%B"],
                cwd=str(local_repo),
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("auto: test commit from engine", log_check.stdout)

            engine.stop()

    def test_engine_handles_non_git_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            non_git_dir = tmp_path / "just_a_folder"
            non_git_dir.mkdir()

            project_cfg = ProjectConfig(
                name="BadProject",
                path=non_git_dir,
                enabled=True,
            )

            engine = BotEngine()
            result = engine.process_project_sync(project_cfg)
            self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()

"""Tests for the redesigned Dark Mode UI components and views."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from src.config.models import ProjectMode
from src.core.engine import BotEngine
from src.core.state import SyncStatus


class TestUIRedesign(unittest.TestCase):
    def _create_git_repo(self, path: Path) -> None:
        subprocess.run(["git", "init", "-b", "main"], cwd=str(path), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Redesign Test"], cwd=str(path), check=True)
        subprocess.run(["git", "config", "user.email", "redesign@test.local"], cwd=str(path), check=True)
        (path / "file.txt").write_text("initial", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=str(path), check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(path), check=True)

    def test_ui_sidebar_metrics_and_filter_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            repo_1 = tmp_path / "repo_active"
            repo_1.mkdir()
            self._create_git_repo(repo_1)

            repo_2 = tmp_path / "repo_paused"
            repo_2.mkdir()
            self._create_git_repo(repo_2)

            config_file = tmp_path / "config.json"
            engine = BotEngine(config_path=config_file)
            engine.start()

            # Add two projects
            engine.add_project("ActiveProj", repo_1, mode=ProjectMode.AUTO)
            engine.add_project("PausedProj", repo_2, mode=ProjectMode.PAUSED)

            status = engine.get_system_status()
            self.assertEqual(status.total_projects, 2)
            self.assertEqual(status.active_projects, 1)
            self.assertEqual(status.paused_projects, 1)

            # Test switching mode
            engine.set_project_mode("PausedProj", ProjectMode.COMMIT_ONLY)
            status_after = engine.get_system_status()
            self.assertEqual(status_after.active_projects, 2)
            self.assertEqual(status_after.paused_projects, 0)

            engine.stop()


if __name__ == "__main__":
    unittest.main()

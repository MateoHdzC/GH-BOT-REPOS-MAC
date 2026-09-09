"""Tests for the UI controller and BotEngine communication layer."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from src.config.models import ProjectMode
from src.core.engine import BotEngine
from src.core.state import SyncStatus


class TestUIController(unittest.TestCase):
    def _create_git_repo(self, path: Path) -> None:
        subprocess.run(["git", "init", "-b", "main"], cwd=str(path), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "UI Tester"], cwd=str(path), check=True)
        subprocess.run(["git", "config", "user.email", "ui@test.local"], cwd=str(path), check=True)
        (path / "file.txt").write_text("initial", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=str(path), check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(path), check=True)

    def test_ui_engine_full_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            repo_path = tmp_path / "ui_project"
            repo_path.mkdir()
            self._create_git_repo(repo_path)

            config_file = tmp_path / "config.json"
            engine = BotEngine(config_path=config_file)
            engine.start()

            # 1. Add project from UI action
            add_ok, msg, proj = engine.add_project(
                name="UIProject",
                path=repo_path,
                mode=ProjectMode.AUTO,
            )
            self.assertTrue(add_ok)
            self.assertIsNotNone(proj)

            # 2. Query system status for UI rendering
            status = engine.get_system_status()
            self.assertEqual(status.total_projects, 1)
            self.assertEqual(status.active_projects, 1)

            # 3. Change mode from UI action
            mode_ok, mode_msg = engine.set_project_mode("UIProject", ProjectMode.COMMIT_ONLY)
            self.assertTrue(mode_ok)
            p_state = engine.get_project_state("UIProject")
            self.assertEqual(p_state.mode, ProjectMode.COMMIT_ONLY)

            # 4. Manual sync from UI button
            (repo_path / "new.txt").write_text("more data", encoding="utf-8")
            sync_ok, sync_msg = engine.sync_project("UIProject")
            self.assertTrue(sync_ok)
            p_state_after = engine.get_project_state("UIProject")
            self.assertEqual(p_state_after.last_sync_status, SyncStatus.SUCCESS)

            # 5. Remove project from UI action
            remove_ok, remove_msg = engine.remove_project("UIProject")
            self.assertTrue(remove_ok)
            self.assertEqual(engine.get_system_status().total_projects, 0)
            self.assertTrue(repo_path.exists())  # Verify files remain intact

            engine.stop()


if __name__ == "__main__":
    unittest.main()

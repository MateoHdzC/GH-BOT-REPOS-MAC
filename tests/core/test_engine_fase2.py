"""Integration tests for Phase 2 BotEngine: modes (AUTO, COMMIT_ONLY, PAUSED), multi-project isolation, and state."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from src.config.models import ProjectMode
from src.core.engine import BotEngine
from src.core.state import SyncStatus


class TestBotEnginePhase2(unittest.TestCase):
    def _create_git_repo(self, path: Path) -> None:
        subprocess.run(["git", "init", "-b", "main"], cwd=str(path), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Bot Engine Test"], cwd=str(path), check=True)
        subprocess.run(["git", "config", "user.email", "bot@engine.test"], cwd=str(path), check=True)
        init_file = path / "init.txt"
        init_file.write_text("initial content\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=str(path), check=True)
        subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(path), check=True)

    def test_engine_commit_only_mode_does_not_push(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            repo_path = tmp_path / "repo_commit_only"
            repo_path.mkdir()
            self._create_git_repo(repo_path)

            config_file = tmp_path / "config.json"
            engine = BotEngine(config_path=config_file)
            engine.start()

            # Add project in COMMIT_ONLY mode
            success, _, proj = engine.add_project(
                name="CommitOnlyProj",
                path=repo_path,
                mode=ProjectMode.COMMIT_ONLY,
                commit_message="feat: commit only test",
            )
            self.assertTrue(success)

            # Make a file change
            (repo_path / "new_feature.py").write_text("print('hello')", encoding="utf-8")

            # Execute sync
            sync_ok, _ = engine.sync_project("CommitOnlyProj")
            self.assertTrue(sync_ok)

            state = engine.get_project_state("CommitOnlyProj")
            self.assertIsNotNone(state)
            self.assertEqual(state.last_sync_status, SyncStatus.SUCCESS)
            self.assertEqual(state.last_commit_message, "feat: commit only test")
            # In COMMIT_ONLY mode, last_push_at remains None
            self.assertIsNone(state.last_push_at)

            engine.stop()

    def test_engine_paused_mode_skips_automated_sync(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            repo_path = tmp_path / "repo_paused"
            repo_path.mkdir()
            self._create_git_repo(repo_path)

            config_file = tmp_path / "config.json"
            engine = BotEngine(config_path=config_file)
            engine.start()

            # Add project in PAUSED mode
            engine.add_project(
                name="PausedProj",
                path=repo_path,
                mode=ProjectMode.PAUSED,
            )

            # Modify file
            (repo_path / "unwanted_change.txt").write_text("do not commit", encoding="utf-8")

            # Trigger automated process sync (manual=False)
            proj = engine.project_manager.get_project("PausedProj")
            self.assertIsNotNone(proj)
            res = engine.process_project_sync(proj, manual=False)
            self.assertTrue(res)

            state = engine.get_project_state("PausedProj")
            self.assertEqual(state.last_sync_status, SyncStatus.SKIPPED_PAUSED)

            # Verify no commit was created in git
            log_res = subprocess.run(
                ["git", "log", "-1", "--pretty=%B"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(log_res.stdout.strip(), "initial commit")

            engine.stop()

    def test_multi_project_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            repo_a = tmp_path / "repo_a"
            repo_a.mkdir()
            self._create_git_repo(repo_a)

            repo_b = tmp_path / "repo_b"
            repo_b.mkdir()
            self._create_git_repo(repo_b)

            repo_c = tmp_path / "repo_c"
            repo_c.mkdir()
            self._create_git_repo(repo_c)

            config_file = tmp_path / "config.json"
            engine = BotEngine(config_path=config_file)
            engine.start()

            engine.add_project("ProjectA", repo_a, mode=ProjectMode.AUTO, commit_message="feat: a")
            engine.add_project("ProjectB", repo_b, mode=ProjectMode.COMMIT_ONLY, commit_message="feat: b")
            engine.add_project("ProjectC", repo_c, mode=ProjectMode.PAUSED, commit_message="feat: c")

            # Modify all 3
            (repo_a / "a.txt").write_text("change A", encoding="utf-8")
            (repo_b / "b.txt").write_text("change B", encoding="utf-8")
            (repo_c / "c.txt").write_text("change C", encoding="utf-8")

            proj_a = engine.project_manager.get_project("ProjectA")
            proj_b = engine.project_manager.get_project("ProjectB")
            proj_c = engine.project_manager.get_project("ProjectC")

            engine.process_project_sync(proj_a, manual=False)
            engine.process_project_sync(proj_b, manual=False)
            engine.process_project_sync(proj_c, manual=False)

            # Verify Project A committed
            log_a = subprocess.run(["git", "log", "-1", "--pretty=%B"], cwd=str(repo_a), capture_output=True, text=True, check=True)
            self.assertEqual(log_a.stdout.strip(), "feat: a")

            # Verify Project B committed
            log_b = subprocess.run(["git", "log", "-1", "--pretty=%B"], cwd=str(repo_b), capture_output=True, text=True, check=True)
            self.assertEqual(log_b.stdout.strip(), "feat: b")

            # Verify Project C did NOT commit
            log_c = subprocess.run(["git", "log", "-1", "--pretty=%B"], cwd=str(repo_c), capture_output=True, text=True, check=True)
            self.assertEqual(log_c.stdout.strip(), "initial commit")

            # Check system status aggregation
            status = engine.get_system_status()
            self.assertEqual(status.total_projects, 3)
            self.assertEqual(status.active_projects, 2)
            self.assertEqual(status.paused_projects, 1)

            engine.stop()

    def test_github_auth_service_integration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_file = Path(tmp_dir) / "config.json"
            engine = BotEngine(config_path=config_file)
            engine.start()

            status_before = engine.get_github_status()
            self.assertFalse(status_before.connected)

            connect_ok = engine.connect_github("octocat", auth_type="keychain")
            self.assertTrue(connect_ok)

            status_after = engine.get_github_status()
            self.assertTrue(status_after.connected)
            self.assertEqual(status_after.username, "octocat")
            self.assertEqual(status_after.auth_type, "keychain")

            disconnect_ok = engine.disconnect_github()
            self.assertTrue(disconnect_ok)
            self.assertFalse(engine.get_github_status().connected)

            engine.stop()


if __name__ == "__main__":
    unittest.main()

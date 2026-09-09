"""Unit tests for ProjectManager CRUD and validation logic."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from src.config.manager import ConfigManager
from src.config.models import ProjectMode
from src.core.project_manager import ProjectManager
from src.git.git_manager import GitManager
from src.watcher.repo_watcher import WatcherManager


class TestProjectManager(unittest.TestCase):
    def _create_git_repo(self, path: Path) -> None:
        subprocess.run(["git", "init", "-b", "main"], cwd=str(path), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test Bot"], cwd=str(path), check=True)
        subprocess.run(["git", "config", "user.email", "bot@test.local"], cwd=str(path), check=True)
        sample_file = path / "README.md"
        sample_file.write_text("# Test Repo\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=str(path), check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=str(path), check=True)

    def test_add_valid_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            repo_path = tmp_path / "my_repo"
            repo_path.mkdir()
            self._create_git_repo(repo_path)

            config_file = tmp_path / "projects.json"
            cfg_mgr = ConfigManager(config_file)
            git_mgr = GitManager()
            watcher_mgr = WatcherManager(on_sync_triggered=lambda p: None)

            try:
                pm = ProjectManager(cfg_mgr, git_mgr, watcher_mgr)
                success, msg, proj = pm.add_project(
                    name="MyProject",
                    path=repo_path,
                    mode=ProjectMode.AUTO,
                    debounce_seconds=120,
                )

                self.assertTrue(success)
                self.assertIsNotNone(proj)
                self.assertEqual(proj.name, "MyProject")
                self.assertEqual(proj.mode, ProjectMode.AUTO)
                self.assertEqual(proj.debounce_seconds, 120)

                reloaded_config = cfg_mgr.load_config()
                self.assertEqual(len(reloaded_config.projects), 1)
                self.assertEqual(reloaded_config.projects[0].name, "MyProject")
            finally:
                watcher_mgr.stop_all()

    def test_add_project_with_remote_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            repo_path = tmp_path / "repo_remote"
            repo_path.mkdir()
            self._create_git_repo(repo_path)

            config_file = tmp_path / "projects.json"
            cfg_mgr = ConfigManager(config_file)
            git_mgr = GitManager()
            watcher_mgr = WatcherManager(on_sync_triggered=lambda p: None)

            try:
                pm = ProjectManager(cfg_mgr, git_mgr, watcher_mgr)
                success, msg, proj = pm.add_project(
                    name="RemoteRepo",
                    path=repo_path,
                    mode=ProjectMode.AUTO,
                    remote_url="https://github.com/octocat/hello-world.git",
                )
                self.assertTrue(success)
                self.assertIsNotNone(proj)

                configured_url = git_mgr.get_remote_url(repo_path, "origin")
                self.assertEqual(configured_url, "https://github.com/octocat/hello-world.git")
            finally:
                watcher_mgr.stop_all()

    def test_github_username_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_file = Path(tmp_dir) / "projects.json"
            cfg_mgr = ConfigManager(config_file)

            config = cfg_mgr.load_config()
            self.assertIsNone(config.github_username)

            config.github_username = "mateo-developer"
            self.assertTrue(cfg_mgr.save_config(config))

            reloaded = cfg_mgr.load_config()
            self.assertEqual(reloaded.github_username, "mateo-developer")

    def test_add_project_nonexistent_path_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            nonexistent = tmp_path / "does_not_exist"
            config_file = tmp_path / "projects.json"
            watcher_mgr = WatcherManager(lambda p: None)

            try:
                pm = ProjectManager(
                    ConfigManager(config_file),
                    GitManager(),
                    watcher_mgr,
                )
                success, msg, proj = pm.add_project("GhostProject", nonexistent)
                self.assertFalse(success)
                self.assertIn("does not exist", msg.lower())
                self.assertIsNone(proj)
            finally:
                watcher_mgr.stop_all()

    def test_add_project_non_git_dir_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            plain_dir = tmp_path / "not_git"
            plain_dir.mkdir()
            config_file = tmp_path / "projects.json"
            watcher_mgr = WatcherManager(lambda p: None)

            try:
                pm = ProjectManager(
                    ConfigManager(config_file),
                    GitManager(),
                    watcher_mgr,
                )
                success, msg, proj = pm.add_project("PlainDir", plain_dir)
                self.assertFalse(success)
                self.assertIn("not a valid git repository", msg.lower())
                self.assertIsNone(proj)
            finally:
                watcher_mgr.stop_all()

    def test_prevent_duplicate_name_and_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            repo_1 = tmp_path / "repo1"
            repo_1.mkdir()
            self._create_git_repo(repo_1)

            repo_2 = tmp_path / "repo2"
            repo_2.mkdir()
            self._create_git_repo(repo_2)

            config_file = tmp_path / "projects.json"
            watcher_mgr = WatcherManager(lambda p: None)
            try:
                pm = ProjectManager(
                    ConfigManager(config_file),
                    GitManager(),
                    watcher_mgr,
                )

                success, _, proj1 = pm.add_project("ProjectAlpha", repo_1)
                self.assertTrue(success)
                self.assertEqual(proj1.name, "ProjectAlpha")

                dup_name_success, msg_name, proj2 = pm.add_project("ProjectAlpha", repo_2)
                self.assertTrue(dup_name_success)
                self.assertEqual(proj2.name, "ProjectAlpha (2)")

                dup_path_success, msg_path, _ = pm.add_project("ProjectBeta", repo_1)
                self.assertFalse(dup_path_success)
                self.assertIn("already registered", msg_path)
            finally:
                watcher_mgr.stop_all()

    def test_remove_project_preserves_local_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            repo_path = tmp_path / "repo_keep"
            repo_path.mkdir()
            self._create_git_repo(repo_path)

            file_inside = repo_path / "precious_code.py"
            file_inside.write_text("print('critical business logic')", encoding="utf-8")

            config_file = tmp_path / "projects.json"
            watcher_mgr = WatcherManager(lambda p: None)
            try:
                pm = ProjectManager(
                    ConfigManager(config_file),
                    GitManager(),
                    watcher_mgr,
                )

                pm.add_project("ToKeep", repo_path)
                self.assertEqual(len(pm.list_projects()), 1)

                remove_success, remove_msg = pm.remove_project("ToKeep")
                self.assertTrue(remove_success)
                self.assertEqual(len(pm.list_projects()), 0)

                self.assertTrue(repo_path.exists())
                self.assertTrue(file_inside.exists())
                self.assertEqual(
                    file_inside.read_text(encoding="utf-8"),
                    "print('critical business logic')",
                )
                self.assertTrue((repo_path / ".git").exists())
            finally:
                watcher_mgr.stop_all()

    def test_set_project_mode_and_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            repo = tmp_path / "mode_repo"
            repo.mkdir()
            self._create_git_repo(repo)

            config_file = tmp_path / "projects.json"
            watcher_mgr = WatcherManager(lambda p: None)
            try:
                pm = ProjectManager(
                    ConfigManager(config_file),
                    GitManager(),
                    watcher_mgr,
                )

                pm.add_project("ModeTest", repo, mode=ProjectMode.AUTO)
                p = pm.get_project("ModeTest")
                self.assertEqual(p.mode, ProjectMode.AUTO)

                pm.set_project_mode("ModeTest", ProjectMode.COMMIT_ONLY)
                p_updated = pm.get_project("ModeTest")
                self.assertEqual(p_updated.mode, ProjectMode.COMMIT_ONLY)

                pm.set_project_mode("ModeTest", "PAUSED")
                p_paused = pm.get_project("ModeTest")
                self.assertEqual(p_paused.mode, ProjectMode.PAUSED)

                pm.set_project_enabled("ModeTest", False)
                p_disabled = pm.get_project("ModeTest")
                self.assertFalse(p_disabled.enabled)

                pm.set_project_debounce("ModeTest", 3600)
                p_debounce = pm.get_project("ModeTest")
                self.assertEqual(p_debounce.debounce_seconds, 3600)
            finally:
                watcher_mgr.stop_all()


if __name__ == "__main__":
    unittest.main()

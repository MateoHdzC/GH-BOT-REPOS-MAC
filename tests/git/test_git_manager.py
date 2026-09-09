"""Unit and integration tests for GitManager against local Git repositories."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from src.git.git_manager import GitManager


class TestGitManager(unittest.TestCase):
    def _create_git_repo(self, path: Path) -> None:
        subprocess.run(["git", "init", "-b", "main"], cwd=str(path), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test Bot"], cwd=str(path), check=True)
        subprocess.run(["git", "config", "user.email", "bot@example.com"], cwd=str(path), check=True)

    def test_is_git_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            repo_dir = tmp_path / "valid_repo"
            repo_dir.mkdir()
            self._create_git_repo(repo_dir)

            git_mgr = GitManager()
            self.assertTrue(git_mgr.is_git_repo(repo_dir))

            non_repo = tmp_path / "not_a_repo"
            non_repo.mkdir()
            self.assertFalse(git_mgr.is_git_repo(non_repo))

            non_existent = tmp_path / "does_not_exist"
            self.assertFalse(git_mgr.is_git_repo(non_existent))

    def test_git_status_and_staging(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = Path(tmp_dir) / "repo"
            repo_dir.mkdir()
            self._create_git_repo(repo_dir)

            git_mgr = GitManager()

            status = git_mgr.get_status(repo_dir)
            self.assertTrue(status.is_git_repo)
            self.assertFalse(status.has_changes)

            sample_file = repo_dir / "sample.txt"
            sample_file.write_text("Hello World\n", encoding="utf-8")

            status = git_mgr.get_status(repo_dir)
            self.assertTrue(status.has_changes)
            self.assertEqual(status.untracked_files_count, 1)
            self.assertTrue(git_mgr.has_changes(repo_dir))

            stage_res = git_mgr.stage_all(repo_dir)
            self.assertTrue(stage_res.success)
            self.assertTrue(git_mgr.has_staged_changes(repo_dir))

    def test_commit_flow_and_prevent_empty_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = Path(tmp_dir) / "repo"
            repo_dir.mkdir()
            self._create_git_repo(repo_dir)

            git_mgr = GitManager()

            empty_res = git_mgr.commit(repo_dir, message="empty test")
            self.assertTrue(empty_res.success)
            self.assertIn("Nothing to commit", empty_res.stdout)

            file_a = repo_dir / "file_a.md"
            file_a.write_text("Content A\n", encoding="utf-8")
            git_mgr.stage_all(repo_dir)

            commit_res = git_mgr.commit(repo_dir, message="feat: add file_a")
            self.assertTrue(commit_res.success)
            self.assertFalse(git_mgr.has_staged_changes(repo_dir))

            log_res = subprocess.run(
                ["git", "log", "-1", "--pretty=%B"],
                cwd=str(repo_dir),
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("feat: add file_a", log_res.stdout)

    def test_push_failure_handled_gracefully(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = Path(tmp_dir) / "repo"
            repo_dir.mkdir()
            self._create_git_repo(repo_dir)

            git_mgr = GitManager()
            file_b = repo_dir / "file_b.txt"
            file_b.write_text("Content B\n", encoding="utf-8")
            git_mgr.stage_all(repo_dir)
            git_mgr.commit(repo_dir, message="feat: add file_b")

            push_res = git_mgr.push(repo_dir, remote="origin")
            self.assertFalse(push_res.success)
            self.assertIsNotNone(push_res.error_message)

    def test_init_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            plain_dir = Path(tmp_dir) / "brand_new"
            plain_dir.mkdir()
            git_mgr = GitManager()
            self.assertFalse(git_mgr.is_git_repo(plain_dir))

            res = git_mgr.init_repo(plain_dir)
            self.assertTrue(res.success)
            self.assertTrue(git_mgr.is_git_repo(plain_dir))


if __name__ == "__main__":
    unittest.main()

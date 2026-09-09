"""Unit tests for Phase 2 GitManager features: error classification, commit metadata, and remotes."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from src.git.git_manager import GitManager
from src.git.models import GitErrorType


class TestGitManagerPhase2(unittest.TestCase):
    def test_classify_push_error_types(self) -> None:
        git_mgr = GitManager()

        auth_err = "Permission denied (publickey). fatal: Could not read from remote repository."
        self.assertEqual(git_mgr.classify_push_error(auth_err, 128), GitErrorType.AUTH_FAILED)

        token_err = "fatal: Authentication failed for 'https://github.com/user/repo.git/'"
        self.assertEqual(git_mgr.classify_push_error(token_err, 128), GitErrorType.AUTH_FAILED)

        net_err = "fatal: unable to access 'https://github.com/...': Could not resolve host: github.com"
        self.assertEqual(git_mgr.classify_push_error(net_err, 128), GitErrorType.NETWORK_ERROR)

        reject_err = "error: failed to push some refs to '...'\nhint: Updates were rejected because the remote contains work that you do not have locally (fetch first)."
        self.assertEqual(git_mgr.classify_push_error(reject_err, 1), GitErrorType.REJECTED_NON_FAST_FORWARD)

        conflict_err = "error: you have divergent branches and need to specify how to reconcile them."
        self.assertEqual(git_mgr.classify_push_error(conflict_err, 1), GitErrorType.CONFLICT)

        branch_err = "error: src refspec feature-xyz does not match any"
        self.assertEqual(git_mgr.classify_push_error(branch_err, 1), GitErrorType.BRANCH_NOT_FOUND)

        remote_err = "fatal: 'upstream' does not appear to be a git repository"
        self.assertEqual(git_mgr.classify_push_error(remote_err, 128), GitErrorType.REMOTE_NOT_FOUND)

    def test_push_without_remotes_returns_no_remote_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_path = Path(tmp_dir) / "no_remote_repo"
            repo_path.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=str(repo_path), check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=str(repo_path), check=True)
            subprocess.run(["git", "config", "user.email", "test@test.local"], cwd=str(repo_path), check=True)

            (repo_path / "file.txt").write_text("content", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=str(repo_path), check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo_path), check=True)

            git_mgr = GitManager()
            remotes = git_mgr.get_remotes(repo_path)
            self.assertEqual(remotes, [])

            push_res = git_mgr.push(repo_path, remote="origin")
            self.assertFalse(push_res.success)
            self.assertEqual(push_res.error_type, GitErrorType.NO_REMOTE)

    def test_get_last_commit_info(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_path = Path(tmp_dir) / "commit_info_repo"
            repo_path.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=str(repo_path), check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Jane Doe"], cwd=str(repo_path), check=True)
            subprocess.run(["git", "config", "user.email", "jane@doe.com"], cwd=str(repo_path), check=True)

            (repo_path / "init.txt").write_text("hello", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=str(repo_path), check=True)
            subprocess.run(["git", "commit", "-m", "feat: create initial scaffold"], cwd=str(repo_path), check=True)

            git_mgr = GitManager()
            commit_info = git_mgr.get_last_commit_info(repo_path)

            self.assertIsNotNone(commit_info)
            self.assertEqual(commit_info.message, "feat: create initial scaffold")
            self.assertEqual(commit_info.author, "Jane Doe")
            self.assertTrue(len(commit_info.hash) >= 7)


if __name__ == "__main__":
    unittest.main()

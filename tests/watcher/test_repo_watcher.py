"""Unit tests for path filtering and file system event handling."""

import unittest
from dataclasses import dataclass
from unittest.mock import MagicMock

from src.watcher.file_filter import is_path_ignored
from src.watcher.repo_watcher import RepoChangeEventHandler


@dataclass
class SimpleFileEvent:
    src_path: str
    event_type: str = "modified"


class TestRepoWatcher(unittest.TestCase):
    def test_is_path_ignored_rules(self) -> None:
        # Ignored paths
        self.assertTrue(is_path_ignored(".git/HEAD"))
        self.assertTrue(is_path_ignored("/path/to/repo/.git/objects/abc"))
        self.assertTrue(is_path_ignored("some/folder/.DS_Store"))
        self.assertTrue(is_path_ignored(".DS_Store"))
        self.assertTrue(is_path_ignored(".venv/lib/python3.11/site-packages/something.py"))
        self.assertTrue(is_path_ignored("__pycache__/module.cpython-311.pyc"))
        self.assertTrue(is_path_ignored(".env"))
        self.assertTrue(is_path_ignored("config/.env.local"))
        self.assertTrue(is_path_ignored("logs/app.log"))
        self.assertTrue(is_path_ignored("key.pem"))

        # Valid non-ignored paths
        self.assertFalse(is_path_ignored("src/core/engine.py"))
        self.assertFalse(is_path_ignored("README.md"))
        self.assertFalse(is_path_ignored("subfolder/feature/index.ts"))
        self.assertFalse(is_path_ignored("assets/images/logo.png"))

    def test_repo_change_event_handler_dispatches_clean_events(self) -> None:
        callback_mock = MagicMock()
        handler = RepoChangeEventHandler(project_name="TestProj", on_change_detected=callback_mock)

        # Event in .git should be ignored
        git_event = SimpleFileEvent(src_path="/repo/.git/index")
        handler.on_modified(git_event)
        self.assertEqual(callback_mock.call_count, 0)

        # Event on .DS_Store should be ignored
        ds_event = SimpleFileEvent(src_path="/repo/.DS_Store")
        handler.on_modified(ds_event)
        self.assertEqual(callback_mock.call_count, 0)

        # Event on normal file should trigger callback
        valid_event = SimpleFileEvent(src_path="/repo/src/main.py")
        handler.on_modified(valid_event)
        self.assertEqual(callback_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()

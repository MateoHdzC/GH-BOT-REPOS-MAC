"""Unit tests for NetworkMonitor and offline queue synchronization."""

import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from src.config.manager import ConfigManager
from src.config.models import AppConfig, ProjectConfig, ProjectMode
from src.core.engine import BotEngine
from src.core.state import SyncStatus
from src.git.git_manager import GitManager
from src.utils.network import NetworkMonitor


class TestNetworkMonitor(unittest.TestCase):
    def test_network_monitor_status_with_mock_checker(self) -> None:
        status_holder = [True]
        monitor = NetworkMonitor(
            check_interval=0.05,
            checker_func=lambda: status_holder[0],
        )
        self.assertTrue(monitor.check_reachability())
        self.assertTrue(monitor.is_online)

        status_holder[0] = False
        self.assertFalse(monitor.check_reachability())

    def test_network_monitor_callbacks(self) -> None:
        status_holder = [False]
        online_called = []
        offline_called = []

        monitor = NetworkMonitor(
            check_interval=0.05,
            on_online=lambda: online_called.append(True),
            on_offline=lambda: offline_called.append(True),
            checker_func=lambda: status_holder[0],
        )

        monitor.start()
        time.sleep(0.08)

        status_holder[0] = True
        time.sleep(0.12)
        self.assertTrue(len(online_called) >= 1)

        status_holder[0] = False
        time.sleep(0.12)
        self.assertTrue(len(offline_called) >= 1)

        monitor.stop()

    def test_network_monitor_start_and_stop_lifecycle(self) -> None:
        monitor = NetworkMonitor(check_interval=0.1, checker_func=lambda: True)
        self.assertFalse(monitor._is_running)
        monitor.start()
        self.assertTrue(monitor._is_running)
        monitor.stop()
        self.assertFalse(monitor._is_running)


class TestEngineOfflineQueue(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.repo_dir = self.root / "test_repo"
        self.repo_dir.mkdir()
        self.remote_dir = self.root / "remote.git"

        subprocess.run(["git", "init", "--bare", str(self.remote_dir)], check=True, capture_output=True)
        subprocess.run(["git", "init", str(self.repo_dir)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.repo_dir), "remote", "add", "origin", str(self.remote_dir)], check=True, capture_output=True)

        test_file = self.repo_dir / "init.txt"
        test_file.write_text("initial")
        subprocess.run(["git", "-C", str(self.repo_dir), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.repo_dir), "commit", "-m", "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.repo_dir), "push", "-u", "origin", "main"], capture_output=True)

        self.config_path = self.root / "config.json"
        self.config_manager = ConfigManager(self.config_path)

        self.project = ProjectConfig(
            name="OfflineTestProj",
            path=self.repo_dir,
            mode=ProjectMode.AUTO,
            enabled=True,
            remote="origin",
            branch="main",
            debounce_seconds=300,
        )
        app_config = AppConfig(projects=[self.project])
        self.config_manager.save_config(app_config)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_engine_offline_queuing_and_auto_flush(self) -> None:
        is_online_flag = [False]
        network_monitor = NetworkMonitor(
            check_interval=0.05,
            checker_func=lambda: is_online_flag[0],
        )

        engine = BotEngine(
            config_manager=self.config_manager,
            network_monitor=network_monitor,
        )
        engine.start()

        new_file = self.repo_dir / "change.txt"
        new_file.write_text("offline content")

        result = engine.process_project_sync(self.project, manual=False)
        self.assertTrue(result)

        state = engine.get_project_state("OfflineTestProj")
        self.assertIsNotNone(state)
        self.assertTrue(state.is_offline_queued)
        self.assertEqual(state.last_sync_status, SyncStatus.OFFLINE_QUEUED)
        self.assertIn("OfflineTestProj", engine._offline_pending_projects)

        is_online_flag[0] = True
        engine._on_network_reconnected()

        state_after = engine.get_project_state("OfflineTestProj")
        self.assertFalse(state_after.is_offline_queued)
        self.assertEqual(state_after.last_sync_status, SyncStatus.SUCCESS)
        self.assertNotIn("OfflineTestProj", engine._offline_pending_projects)

        engine.stop()


if __name__ == "__main__":
    unittest.main()

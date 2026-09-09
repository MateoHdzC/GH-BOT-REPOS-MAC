"""Unit tests for SingleInstanceLock utility."""

import os
import tempfile
import unittest
from pathlib import Path

from src.utils.process_lock import SingleInstanceLock


class TestSingleInstanceLock(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.lock_file = Path(self.temp_dir.name) / "test_app.lock"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_acquire_and_release(self) -> None:
        lock = SingleInstanceLock(lock_path=self.lock_file)
        self.assertFalse(lock.is_locked)

        acquired = lock.acquire()
        self.assertTrue(acquired)
        self.assertTrue(lock.is_locked)
        self.assertTrue(self.lock_file.exists())
        self.assertEqual(lock.get_running_pid(), os.getpid())

        lock.release()
        self.assertFalse(lock.is_locked)

    def test_context_manager(self) -> None:
        with SingleInstanceLock(lock_path=self.lock_file) as lock:
            self.assertTrue(lock.is_locked)
            self.assertEqual(lock.get_running_pid(), os.getpid())

        self.assertFalse(lock.is_locked)

    def test_prevent_duplicate_instance(self) -> None:
        lock_instance_1 = SingleInstanceLock(lock_path=self.lock_file)
        lock_instance_2 = SingleInstanceLock(lock_path=self.lock_file)

        self.assertTrue(lock_instance_1.acquire())
        self.assertTrue(lock_instance_1.is_locked)

        self.assertFalse(lock_instance_2.acquire())
        self.assertFalse(lock_instance_2.is_locked)
        self.assertEqual(lock_instance_2.get_running_pid(), os.getpid())

        lock_instance_1.release()

        self.assertTrue(lock_instance_2.acquire())
        self.assertTrue(lock_instance_2.is_locked)
        lock_instance_2.release()

    def test_reacquire_same_instance(self) -> None:
        lock = SingleInstanceLock(lock_path=self.lock_file)
        self.assertTrue(lock.acquire())
        self.assertTrue(lock.acquire())
        lock.release()

    def test_release_unacquired(self) -> None:
        lock = SingleInstanceLock(lock_path=self.lock_file)
        try:
            lock.release()
        except Exception as e:
            self.fail(f"Releasing an unacquired lock should not raise an exception: {e}")

    def test_get_running_pid_nonexistent(self) -> None:
        non_existent = Path(self.temp_dir.name) / "non_existent.lock"
        lock = SingleInstanceLock(lock_path=non_existent)
        self.assertIsNone(lock.get_running_pid())


if __name__ == "__main__":
    unittest.main()

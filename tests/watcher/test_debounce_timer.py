"""Unit tests for the thread-safe DebounceTimer."""

import time
import unittest

from src.watcher.debounce_timer import DebounceTimer


class TestDebounceTimer(unittest.TestCase):
    def test_debounce_timer_fires_after_inactivity(self) -> None:
        call_count = 0

        def callback() -> None:
            nonlocal call_count
            call_count += 1

        timer = DebounceTimer(interval_seconds=0.15, callback=callback)
        self.assertFalse(timer.is_active)

        timer.trigger()
        self.assertTrue(timer.is_active)

        time.sleep(0.25)

        self.assertEqual(call_count, 1)
        self.assertFalse(timer.is_active)

    def test_debounce_timer_resets_on_consecutive_triggers(self) -> None:
        call_count = 0

        def callback() -> None:
            nonlocal call_count
            call_count += 1

        timer = DebounceTimer(interval_seconds=0.2, callback=callback)

        # Trigger at t=0
        timer.trigger()
        time.sleep(0.1)

        # Trigger again at t=0.1 (should reset the 0.2s countdown)
        timer.trigger()
        time.sleep(0.1)

        # Trigger again at t=0.2 (should reset the 0.2s countdown)
        timer.trigger()
        time.sleep(0.1)

        # At this point, callback should NOT have fired yet
        self.assertEqual(call_count, 0)

        # Wait for the full quiet period (0.25s > 0.2s)
        time.sleep(0.25)

        self.assertEqual(call_count, 1)

    def test_debounce_timer_cancel(self) -> None:
        call_count = 0

        def callback() -> None:
            nonlocal call_count
            call_count += 1

        timer = DebounceTimer(interval_seconds=0.15, callback=callback)
        timer.trigger()
        self.assertTrue(timer.is_active)

        timer.cancel()
        self.assertFalse(timer.is_active)

        time.sleep(0.2)
        self.assertEqual(call_count, 0)


if __name__ == "__main__":
    unittest.main()

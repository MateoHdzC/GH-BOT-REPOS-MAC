"""Thread-safe debounce timer that delays callback execution until inactivity."""

import threading
from typing import Callable, Optional

from src.utils.logger import get_logger

logger = get_logger("timer")


class DebounceTimer:
    """Thread-safe debouncer that waits for a quiet period before invoking a callback."""

    def __init__(
        self,
        interval_seconds: float,
        callback: Callable[[], None],
        name: str = "DebounceTimer",
    ) -> None:
        self.interval_seconds = max(0.1, interval_seconds)
        self.callback = callback
        self.name = name
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        self._is_active = False

    def trigger(self) -> None:
        """Starts or resets the countdown timer.

        If a timer is already running, it is cancelled and a fresh timer is started.
        """
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                logger.debug(f"[{self.name}] Debounce timer reset ({self.interval_seconds}s remaining).")
            else:
                logger.info(f"[{self.name}] Debounce timer started for {self.interval_seconds}s.")

            self._is_active = True
            self._timer = threading.Timer(self.interval_seconds, self._on_timeout)
            self._timer.daemon = True
            self._timer.start()

    def _on_timeout(self) -> None:
        """Internal callback invoked when the timer expires with no new events."""
        with self._lock:
            self._timer = None
            self._is_active = False

        logger.info(f"[{self.name}] Debounce period elapsed ({self.interval_seconds}s without changes). Executing callback.")
        try:
            self.callback()
        except Exception as err:
            logger.error(f"[{self.name}] Unhandled exception during callback execution: {err}", exc_info=True)

    def cancel(self) -> None:
        """Cancels any running timer without firing the callback."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
                self._is_active = False
                logger.debug(f"[{self.name}] Debounce timer cancelled.")

    @property
    def is_active(self) -> bool:
        """Returns True if a debounce countdown is currently active."""
        with self._lock:
            return self._is_active

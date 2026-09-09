"""Single-instance process locking mechanism using Unix fcntl.flock."""

import fcntl
import os
from pathlib import Path
from typing import Optional

from src.utils.constants import DEFAULT_LOCK_PATH
from src.utils.logger import get_logger

logger = get_logger("lock")


class SingleInstanceLock:
    """Manages an exclusive non-blocking file lock to prevent duplicate process instances."""

    def __init__(self, lock_path: Optional[Path] = None) -> None:
        self.lock_path: Path = Path(lock_path) if lock_path else DEFAULT_LOCK_PATH
        self._file = None
        self._is_locked: bool = False

    @property
    def is_locked(self) -> bool:
        return self._is_locked

    def acquire(self) -> bool:
        """Attempts to acquire an exclusive lock. Returns True on success, False if already held."""
        if self._is_locked:
            return True

        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            self._file = open(self.lock_path, "a+", encoding="utf-8")
            fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._file.seek(0)
            self._file.truncate()
            self._file.write(f"{os.getpid()}\n")
            self._file.flush()
            self._is_locked = True
            logger.debug(f"[LOCK] Acquired single-instance lock at {self.lock_path} (PID: {os.getpid()})")
            return True
        except (BlockingIOError, IOError, OSError) as err:
            running_pid = self.get_running_pid()
            logger.warning(
                f"[LOCK] Another instance of the application is already running "
                f"(Lock: {self.lock_path}, PID: {running_pid or 'unknown'}). Detail: {err}"
            )
            self._close_file()
            self._is_locked = False
            return False

    def release(self) -> None:
        """Releases the lock and closes the underlying file descriptor."""
        if not self._is_locked or self._file is None:
            return

        try:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
            logger.debug(f"[LOCK] Released single-instance lock at {self.lock_path}")
        except (IOError, OSError) as err:
            logger.error(f"[LOCK] Error releasing lock: {err}")
        finally:
            self._close_file()
            self._is_locked = False

    def get_running_pid(self) -> Optional[int]:
        """Reads the PID stored in the lock file if accessible."""
        if not self.lock_path.exists():
            return None
        try:
            content = self.lock_path.read_text(encoding="utf-8").strip()
            if content.isdigit():
                return int(content)
        except Exception:
            pass
        return None

    def _close_file(self) -> None:
        if self._file is not None:
            try:
                self._file.close()
            except Exception:
                pass
            self._file = None

    def __enter__(self) -> "SingleInstanceLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()

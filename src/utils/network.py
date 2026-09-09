"""Network reachability monitor and offline event dispatcher for macOS."""

import socket
import threading
from typing import Callable, Optional

from src.utils.logger import get_logger

logger = get_logger("network")


class NetworkMonitor:
    """Monitors internet and GitHub reachability and dispatches connectivity events."""

    def __init__(
        self,
        host: str = "github.com",
        port: int = 443,
        check_interval: float = 10.0,
        timeout: float = 1.5,
        on_online: Optional[Callable[[], None]] = None,
        on_offline: Optional[Callable[[], None]] = None,
        checker_func: Optional[Callable[[], bool]] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.check_interval = check_interval
        self.timeout = timeout
        self.checker_func = checker_func
        self._on_online_callbacks: list[Callable[[], None]] = [on_online] if on_online else []
        self._on_offline_callbacks: list[Callable[[], None]] = [on_offline] if on_offline else []

        self._is_online: bool = True
        self._is_running: bool = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    @property
    def is_online(self) -> bool:
        with self._lock:
            return self._is_online

    def add_on_online_listener(self, callback: Callable[[], None]) -> None:
        if callback not in self._on_online_callbacks:
            self._on_online_callbacks.append(callback)

    def add_on_offline_listener(self, callback: Callable[[], None]) -> None:
        if callback not in self._on_offline_callbacks:
            self._on_offline_callbacks.append(callback)

    def check_reachability(self) -> bool:
        """Performs a direct TCP handshake to verify reachability."""
        if self.checker_func is not None:
            try:
                return bool(self.checker_func())
            except Exception:
                return False

        try:
            sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
            sock.close()
            return True
        except (socket.timeout, socket.gaierror, ConnectionRefusedError, OSError):
            return False

    def start(self) -> None:
        """Starts the background reachability polling thread."""
        if self._is_running:
            return
        self._is_running = True
        self._stop_event.clear()
        self._is_online = self.check_reachability()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="NetworkReachabilityMonitor",
            daemon=True,
        )
        self._monitor_thread.start()
        logger.debug(
            f"[NETWORK] NetworkMonitor started (initial status: {'ONLINE' if self._is_online else 'OFFLINE'})"
        )

    def stop(self) -> None:
        """Stops the background reachability polling thread."""
        if not self._is_running:
            return
        self._is_running = False
        self._stop_event.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)
        self._monitor_thread = None
        logger.debug("[NETWORK] NetworkMonitor stopped.")

    def _monitor_loop(self) -> None:
        while self._is_running and not self._stop_event.is_set():
            current_status = self.check_reachability()
            transition_to_online = False
            transition_to_offline = False

            with self._lock:
                previous_status = self._is_online
                self._is_online = current_status
                if not previous_status and current_status:
                    transition_to_online = True
                elif previous_status and not current_status:
                    transition_to_offline = True

            if transition_to_online:
                logger.info("[NETWORK] Internet reachability restored. Dispatching online listeners...")
                for cb in list(self._on_online_callbacks):
                    try:
                        cb()
                    except Exception as err:
                        logger.error(f"[NETWORK] Error in online callback: {err}")

            if transition_to_offline:
                logger.warning("[NETWORK] Internet reachability lost. Entering offline queue mode.")
                for cb in list(self._on_offline_callbacks):
                    try:
                        cb()
                    except Exception as err:
                        logger.error(f"[NETWORK] Error in offline callback: {err}")

            self._stop_event.wait(self.check_interval)

"""File system watcher monitoring local repositories with watchdog and standard library fallback."""

import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

from src.config.models import ProjectConfig, ProjectMode
from src.utils.logger import get_logger
from src.watcher.debounce_timer import DebounceTimer
from src.watcher.file_filter import is_path_ignored

logger = get_logger("watcher")

try:
    from watchdog.events import FileSystemEvent, FileSystemEventHandler
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    FileSystemEventHandler = object
    FileSystemEvent = Any
    Observer = Any


if WATCHDOG_AVAILABLE:

    class RepoChangeEventHandler(FileSystemEventHandler):
        """Event handler that filters file system events and triggers a debounce timer."""

        def __init__(
            self, project_name: str, on_change_detected: Callable[[], None]
        ) -> None:
            super().__init__()
            self.project_name = project_name
            self.on_change_detected = on_change_detected

        def _handle_event(self, event: Any) -> None:
            src_path = getattr(event, "src_path", "")
            dest_path = getattr(event, "dest_path", "")

            if is_path_ignored(src_path) or (dest_path and is_path_ignored(dest_path)):
                return

            event_type = getattr(event, "event_type", "modified")
            logger.info(
                f"[WATCHER] [{self.project_name}] Change detected: {event_type} on {src_path}"
            )
            self.on_change_detected()

        def on_created(self, event: Any) -> None:
            self._handle_event(event)

        def on_modified(self, event: Any) -> None:
            self._handle_event(event)

        def on_deleted(self, event: Any) -> None:
            self._handle_event(event)

        def on_moved(self, event: Any) -> None:
            self._handle_event(event)

else:

    class RepoChangeEventHandler:
        """Mock/fallback event handler when watchdog is not installed."""

        def __init__(
            self, project_name: str, on_change_detected: Callable[[], None]
        ) -> None:
            self.project_name = project_name
            self.on_change_detected = on_change_detected

        def _handle_event(self, event: Any) -> None:
            src_path = getattr(event, "src_path", "")
            if is_path_ignored(src_path):
                return
            self.on_change_detected()

        def on_created(self, event: Any) -> None:
            self._handle_event(event)

        def on_modified(self, event: Any) -> None:
            self._handle_event(event)

        def on_deleted(self, event: Any) -> None:
            self._handle_event(event)

        def on_moved(self, event: Any) -> None:
            self._handle_event(event)


class PollingRepoObserver:
    """Standard-library fallback observer using mtime polling when watchdog is unavailable."""

    def __init__(
        self,
        path: Path,
        on_change: Callable[[], None],
        poll_interval: float = 0.5,
    ) -> None:
        self.path = path
        self.on_change = on_change
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._snapshot: dict[str, float] = {}

    def _take_snapshot(self) -> dict[str, float]:
        snapshot: dict[str, float] = {}
        if not self.path.exists():
            return snapshot

        for root, dirs, files in os.walk(self.path):
            dirs[:] = [
                d
                for d in dirs
                if not is_path_ignored(os.path.join(root, d))
            ]
            for file in files:
                full_path = os.path.join(root, file)
                if not is_path_ignored(full_path):
                    try:
                        snapshot[full_path] = os.path.getmtime(full_path)
                    except OSError:
                        pass
        return snapshot

    def _poll_loop(self) -> None:
        self._snapshot = self._take_snapshot()
        while not self._stop_event.is_set():
            if self._stop_event.wait(self.poll_interval):
                break
            current_snapshot = self._take_snapshot()
            if current_snapshot != self._snapshot:
                self._snapshot = current_snapshot
                self.on_change()

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
            self._thread = None


class RepoWatcher:
    """Monitors a single project repository directory and debounces sync triggers."""

    def __init__(
        self,
        project: ProjectConfig,
        on_sync_triggered: Callable[[ProjectConfig], None],
    ) -> None:
        self.project = project
        self.on_sync_triggered = on_sync_triggered
        self.resolved_path = project.resolved_path()

        self.timer = DebounceTimer(
            interval_seconds=project.debounce_seconds,
            callback=self._on_debounce_elapsed,
            name=f"Timer-{project.name}",
        )
        self._observer: Any = None
        self._is_running = False

    def _on_debounce_elapsed(self) -> None:
        """Invoked by the debounce timer when the quiet period elapses."""
        if not self.project.enabled or self.project.mode == ProjectMode.PAUSED:
            logger.info(
                f"[PROJECT] [{self.project.name}] Debounce elapsed but project is {self.project.mode.value} (enabled={self.project.enabled}). Skipping."
            )
            return
        self.on_sync_triggered(self.project)

    def _on_file_changed(self) -> None:
        """Invoked whenever a non-ignored file system event is detected."""
        if not self.project.enabled or self.project.mode == ProjectMode.PAUSED:
            logger.debug(
                f"[PROJECT] [{self.project.name}] Change ignored because project is {self.project.mode.value} (enabled={self.project.enabled})."
            )
            return
        self.timer.trigger()

    def update_project_config(self, new_config: ProjectConfig) -> None:
        """Updates internal project configuration without restarting the watcher process."""
        old_mode = self.project.mode
        self.project = new_config
        self.timer.interval_seconds = max(0.1, new_config.debounce_seconds)

        if new_config.mode == ProjectMode.PAUSED or not new_config.enabled:
            if self.timer.is_active:
                logger.info(f"[PROJECT] [{new_config.name}] Cancelling active debounce timer due to mode switch to {new_config.mode.value}.")
                self.timer.cancel()
        elif old_mode == ProjectMode.PAUSED and new_config.mode != ProjectMode.PAUSED:
            logger.info(f"[PROJECT] [{new_config.name}] Project unpaused (Mode: {new_config.mode.value}). Watcher active.")

    def start(self) -> bool:
        """Starts monitoring the target directory."""
        if self._is_running:
            return True

        if not self.resolved_path.exists():
            logger.error(
                f"[WATCHER] [ERROR] [{self.project.name}] Cannot start watcher: Directory {self.resolved_path} does not exist."
            )
            return False

        try:
            if WATCHDOG_AVAILABLE:
                event_handler = RepoChangeEventHandler(
                    project_name=self.project.name,
                    on_change_detected=self._on_file_changed,
                )
                self._observer = Observer()
                self._observer.schedule(
                    event_handler,
                    path=str(self.resolved_path),
                    recursive=True,
                )
                self._observer.start()
                logger.info(
                    f"[WATCHER] [{self.project.name}] Watcher started using native FSEvents/watchdog on {self.resolved_path} (mode: {self.project.mode.value}, debounce: {self.project.debounce_seconds}s)"
                )
            else:
                self._observer = PollingRepoObserver(
                    path=self.resolved_path,
                    on_change=self._on_file_changed,
                )
                self._observer.start()
                logger.info(
                    f"[WATCHER] [{self.project.name}] Watcher started using standard polling observer on {self.resolved_path} (mode: {self.project.mode.value}, debounce: {self.project.debounce_seconds}s)"
                )

            self._is_running = True
            return True
        except Exception as err:
            logger.error(
                f"[WATCHER] [ERROR] [{self.project.name}] Failed to start file observer: {err}",
                exc_info=True,
            )
            self._is_running = False
            return False

    def stop(self) -> None:
        """Stops the file observer and cancels any pending debounce timers."""
        self.timer.cancel()
        if self._observer is not None and self._is_running:
            try:
                self._observer.stop()
                if hasattr(self._observer, "join"):
                    self._observer.join(timeout=2.0)
            except Exception as err:
                logger.warning(f"[WATCHER] [{self.project.name}] Error stopping observer: {err}")
            finally:
                self._observer = None
                self._is_running = False
            logger.info(f"[WATCHER] [{self.project.name}] Watcher stopped.")

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def is_timer_running(self) -> bool:
        return self.timer.is_active


class WatcherManager:
    """Manages active RepoWatcher instances across all configured projects."""

    def __init__(self, on_sync_triggered: Callable[[ProjectConfig], None]) -> None:
        self.on_sync_triggered = on_sync_triggered
        self._watchers: dict[str, RepoWatcher] = {}

    def get_watcher(self, project_name: str) -> Optional[RepoWatcher]:
        """Retrieves active watcher instance for a specific project."""
        return self._watchers.get(project_name)

    def add_or_update_watcher(self, project: ProjectConfig) -> bool:
        """Registers a new watcher or updates the existing project configuration."""
        if project.name in self._watchers:
            watcher = self._watchers[project.name]
            watcher.update_project_config(project)
            if not project.enabled and watcher.is_running:
                watcher.stop()
            elif project.enabled and not watcher.is_running:
                watcher.start()
            return True

        if not project.enabled:
            logger.info(f"[PROJECT] [{project.name}] Project is disabled. Not starting watcher.")
            return True

        watcher = RepoWatcher(
            project=project,
            on_sync_triggered=self.on_sync_triggered,
        )
        if watcher.start():
            self._watchers[project.name] = watcher
            return True
        return False

    def remove_watcher(self, project_name: str) -> None:
        """Stops and unregisters a watcher by project name."""
        if project_name in self._watchers:
            watcher = self._watchers.pop(project_name)
            watcher.stop()
            logger.info(f"[PROJECT] [{project_name}] Watcher removed cleanly.")

    def register_projects(self, projects: list[ProjectConfig]) -> None:
        """Registers and starts watchers for the provided projects list."""
        self.stop_all()
        for project in projects:
            self.add_or_update_watcher(project)

    def stop_all(self) -> None:
        """Stops all registered watchers cleanly."""
        for name, watcher in list(self._watchers.items()):
            watcher.stop()
        self._watchers.clear()

    def get_active_count(self) -> int:
        """Returns the number of actively running watchers."""
        return sum(1 for w in self._watchers.values() if w.is_running)

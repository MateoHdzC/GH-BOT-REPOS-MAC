"""Central orchestrator engine coordinating project management, watchers, and Git sync."""

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from src.config.manager import ConfigManager
from src.config.models import AppConfig, ProjectConfig, ProjectMode
from src.core.github_service import GitHubAuthService, GitHubAuthStatus
from src.core.project_manager import ProjectManager
from src.core.state import ProjectRuntimeState, SyncStatus, SystemStatus
from src.git.git_manager import GitManager
from src.git.secret_scanner import SecretScanner
from src.utils.logger import get_logger
from src.utils.network import NetworkMonitor
from src.watcher.repo_watcher import WatcherManager

logger = get_logger("engine")


class BotEngine:
    """Core automation engine managing project watchers, state, and Git pipelines."""

    def __init__(
        self,
        config_path: Optional[Path] = None,
        git_manager: Optional[GitManager] = None,
        config_manager: Optional[ConfigManager] = None,
        network_monitor: Optional[NetworkMonitor] = None,
        secret_scanner: Optional[SecretScanner] = None,
    ) -> None:
        self.config_manager = config_manager or ConfigManager(config_path)
        self.git_manager = git_manager or GitManager()
        self.watcher_manager = WatcherManager(on_sync_triggered=self.process_project_sync)
        self.github_service = GitHubAuthService()
        self.secret_scanner = secret_scanner or SecretScanner()
        self.network_monitor = network_monitor or NetworkMonitor(
            on_online=self._on_network_reconnected
        )
        self._offline_pending_projects: set[str] = set()
        self._offline_lock = threading.Lock()

        self._states: dict[str, ProjectRuntimeState] = {}
        self._states_lock = threading.RLock()
        self._start_time: float = time.time()
        self._is_running = False

        self.project_manager = ProjectManager(
            config_manager=self.config_manager,
            git_manager=self.git_manager,
            watcher_manager=self.watcher_manager,
            on_project_changed=self._on_project_changed,
            on_project_removed=self._on_project_removed,
        )

    @property
    def config(self) -> AppConfig:
        return self.project_manager.config

    def _get_or_create_state(self, project: ProjectConfig) -> ProjectRuntimeState:
        with self._states_lock:
            if project.name not in self._states:
                branch = self.git_manager.get_current_branch(project.resolved_path())
                last_commit = self.git_manager.get_last_commit_info(project.resolved_path())
                self._states[project.name] = ProjectRuntimeState(
                    name=project.name,
                    path=str(project.path),
                    mode=project.mode,
                    enabled=project.enabled,
                    debounce_seconds=project.debounce_seconds,
                    current_branch=branch,
                    last_commit_hash=last_commit.hash if last_commit else None,
                    last_commit_message=last_commit.message if last_commit else None,
                    last_commit_at=last_commit.timestamp if last_commit else None,
                )
            return self._states[project.name]

    def _on_project_changed(self, project: ProjectConfig) -> None:
        with self._states_lock:
            state = self._states.get(project.name)
            if state:
                state.mode = project.mode
                state.enabled = project.enabled
                state.path = str(project.path)
                state.debounce_seconds = project.debounce_seconds
            else:
                self._get_or_create_state(project)

    def _on_project_removed(self, project_name: str) -> None:
        """Callback invoked when a project is removed."""
        with self._states_lock:
            self._states.pop(project_name, None)

    def start(self) -> bool:
        """Initializes runtime state and starts watching all configured repositories."""
        logger.info("[SYSTEM] Initializing GH-BOT-REPOS-MAC daemon engine...")
        self._start_time = time.time()
        self.project_manager.reload_config()

        enabled_projects = self.config.get_enabled_projects()
        if not enabled_projects:
            logger.warning(
                "[SYSTEM] No enabled projects found in configuration. Bot will idle."
            )

        for project in self.config.projects:
            resolved = project.resolved_path()
            state = self._get_or_create_state(project)

            if not resolved.exists():
                logger.error(
                    f"[PROJECT] [ERROR] [{project.name}] Configured directory does not exist: {resolved}"
                )
                state.last_error = f"Directory not found: {resolved}"
            elif not self.git_manager.is_git_repo(resolved):
                logger.warning(
                    f"[PROJECT] [ERROR] [{project.name}] Directory is not a valid Git repository: {resolved}"
                )
                state.last_error = f"Not a valid Git repository: {resolved}"
            else:
                branch = self.git_manager.get_current_branch(resolved)
                state.current_branch = branch
                logger.info(
                    f"[PROJECT] Verified Git repository '{project.name}' at {resolved} (Branch: {branch or 'unknown'}, Mode: {project.mode.value})"
                )

        if self.config.github_username and not self.github_service.is_connected():
            self.github_service.connect(self.config.github_username, auth_type="keychain")

        self.watcher_manager.register_projects(enabled_projects)
        self.network_monitor.start()
        self._is_running = True
        logger.info(
            f"[SYSTEM] GH-BOT-REPOS-MAC engine running. Watching {self.watcher_manager.get_active_count()} active project(s)."
        )
        return True

    def process_project_sync(
        self,
        project: ProjectConfig,
        manual: bool = False,
    ) -> bool:
        """Executes the automated or manual Git pipeline for a single repository.

        Workflow:
            1. Validate mode (if PAUSED and not manual -> skip).
            2. Validate Git repository existence.
            3. git status -> inspect changes.
            4. git add . -> stage changes.
            5. Check for real staged changes (prevent empty commits).
            6. git commit -> commit changes.
            7. If mode allows push (AUTO or manual) -> git push.
            8. Update ProjectRuntimeState.
        """
        resolved_path = project.resolved_path()
        state = self._get_or_create_state(project)

        if project.mode == ProjectMode.PAUSED and not manual:
            logger.info(f"[PROJECT] [{project.name}] Sync skipped: project is PAUSED.")
            state.last_sync_status = SyncStatus.SKIPPED_PAUSED
            return True

        if not project.enabled and not manual:
            logger.info(f"[PROJECT] [{project.name}] Sync skipped: project is disabled.")
            return True

        trigger_type = "Manual" if manual else "Automated"
        logger.info(
            f"[GIT] [{project.name}] Starting {trigger_type} Git pipeline on {resolved_path} (Mode: {project.mode.value})"
        )
        state.last_sync_status = SyncStatus.SYNCING

        try:
            if not self.git_manager.is_git_repo(resolved_path):
                err_msg = f"{resolved_path} is not a valid Git repository."
                logger.error(f"[GIT] [ERROR] [{project.name}] Pipeline aborted: {err_msg}")
                state.last_error = err_msg
                state.last_sync_status = SyncStatus.ERROR
                return False

            state.current_branch = self.git_manager.get_current_branch(resolved_path)

            initial_status = self.git_manager.get_status(resolved_path)
            logger.debug(
                f"[GIT] [{project.name}] Initial status - Changes: {initial_status.has_changes}, Untracked: {initial_status.untracked_files_count}"
            )

            stage_result = self.git_manager.stage_all(resolved_path)
            if not stage_result.success:
                err_msg = stage_result.error_message or "Staging failed"
                logger.error(f"[GIT] [ERROR] [{project.name}] {err_msg}")
                state.last_error = err_msg
                state.last_sync_status = SyncStatus.STAGING_FAILED
                return False

            has_staged = self.git_manager.has_staged_changes(resolved_path)
            if has_staged:
                staged_diff = self.git_manager.get_staged_diff(resolved_path)
                secrets_found = self.secret_scanner.scan_diff(staged_diff)
                if secrets_found:
                    rule_names = ", ".join(sorted({s.rule_name for s in secrets_found}))
                    err_msg = f"Se detectaron credenciales ({rule_names}). Commit cancelado automáticamente por seguridad."
                    logger.critical(f"[SECURITY] [{project.name}] {err_msg}")
                    self.git_manager.unstage_all(resolved_path)
                    state.last_error = err_msg
                    state.last_error_type = "SECRET_DETECTED"
                    state.last_sync_status = SyncStatus.COMMIT_FAILED
                    from src.utils.notifications import send_macos_notification

                    send_macos_notification(
                        message=f"Bloqueado por seguridad en {project.name}: {rule_names}",
                        subtitle="Alerta de Credenciales",
                        sound=True,
                    )
                    return False

                now_str = datetime.now().isoformat()
                commit_result = self.git_manager.commit(
                    resolved_path,
                    message=project.commit_message,
                )
                if not commit_result.success:
                    err_msg = commit_result.error_message or "Commit failed"
                    logger.error(f"[COMMIT] [ERROR] [{project.name}] {err_msg}")
                    state.last_error = err_msg
                    state.last_sync_status = SyncStatus.COMMIT_FAILED
                    return False

                commit_info = self.git_manager.get_last_commit_info(resolved_path)
                state.last_commit_at = now_str
                if commit_info:
                    state.last_commit_hash = commit_info.hash
                    state.last_commit_message = commit_info.message

                logger.info(
                    f"[COMMIT] [{project.name}] Commit created successfully: {commit_result.stdout}"
                )
            else:
                logger.info(f"[GIT] [{project.name}] No new uncommitted changes found in working tree.")

            should_push = (project.mode == ProjectMode.AUTO) or (manual and project.mode != ProjectMode.COMMIT_ONLY)

            if should_push:
                if not self.network_monitor.is_online:
                    logger.info(
                        f"[NETWORK] [{project.name}] Network is offline. Push queued until connectivity is restored."
                    )
                    with self._offline_lock:
                        self._offline_pending_projects.add(project.name)
                    state.is_offline_queued = True
                    state.last_sync_status = SyncStatus.OFFLINE_QUEUED
                    state.last_error = "Sin conexión a Internet. Sincronización encolada para cuando vuelva la red."
                    state.last_error_type = "OFFLINE"
                    return True

                remotes = self.git_manager.get_remotes(resolved_path)
                if not remotes:
                    err_msg = f"El repositorio no tiene remoto '{project.remote}' configurado. Agrega la URL de GitHub en el proyecto."
                    logger.warning(f"[PUSH] [ERROR] [{project.name}] {err_msg}")
                    state.last_error = err_msg
                    state.last_error_type = "NO_REMOTE"
                    state.last_sync_status = SyncStatus.PUSH_FAILED
                    return not manual

                push_result = self.git_manager.push(
                    resolved_path,
                    remote=project.remote,
                    branch=project.branch,
                    token=self.github_service.get_token(),
                    username=self.github_service.get_username(),
                )
                if not push_result.success:
                    state.last_error = push_result.error_message
                    state.last_error_type = (
                        push_result.error_type.value if push_result.error_type else None
                    )
                    state.last_sync_status = SyncStatus.PUSH_FAILED
                    logger.warning(
                        f"[PUSH] [ERROR] [{project.name}] Push was not completed: {push_result.error_message}."
                    )
                    from src.utils.notifications import send_macos_notification

                    err_label = push_result.error_type.value if push_result.error_type else "Error"
                    send_macos_notification(
                        message=f"Fallo al hacer push en {project.name}: {push_result.error_message}",
                        subtitle=f"Estado: {err_label}",
                        sound=True,
                    )
                    return not manual

                with self._offline_lock:
                    self._offline_pending_projects.discard(project.name)
                state.is_offline_queued = False
                state.last_push_at = datetime.now().isoformat()
                state.last_sync_status = SyncStatus.SUCCESS
                state.last_error = None
                state.last_error_type = None
                logger.info(f"[PUSH] [{project.name}] Push completed successfully to {project.remote}.")
                from src.utils.notifications import send_macos_notification

                send_macos_notification(
                    message=f"Cambios subidos exitosamente en {project.name}",
                    subtitle="Push completado",
                )
            else:
                logger.info(
                    f"[PUSH] [{project.name}] Push skipped: project is in {project.mode.value} mode."
                )
                state.last_sync_status = SyncStatus.SUCCESS if has_staged else SyncStatus.NO_CHANGES
                state.last_error = None
                state.last_error_type = None

            logger.info(f"[SYSTEM] [{project.name}] Git pipeline finished successfully.")
            return True

        except Exception as err:
            logger.error(
                f"[SYSTEM] [ERROR] [{project.name}] Unexpected error during Git pipeline: {err}",
                exc_info=True,
            )
            state.last_error = str(err)
            state.last_sync_status = SyncStatus.ERROR
            return False


    def sync_project(self, project_name: str) -> tuple[bool, str]:
        """Manually triggers the Git pipeline for a project (UI 'SUBIR AHORA' action)."""
        project = self.project_manager.get_project(project_name)
        if not project:
            return False, f"Project '{project_name}' not found."

        success = self.process_project_sync(project, manual=True)
        state = self.get_project_state(project_name)
        if not success:
            err_msg = state.last_error if state and state.last_error else "Error desconocido durante la sincronización."
            return False, f"Fallo al subir '{project_name}': {err_msg}"

        return True, f"Proyecto '{project_name}' sincronizado y subido correctamente a GitHub."

    def init_git_repo(self, path: Union[str, Path]) -> tuple[bool, str]:
        """Initializes a new Git repository at the given directory path."""
        raw_path = Path(path)
        resolved_path = raw_path.expanduser().resolve()
        if not resolved_path.exists():
            return False, f"Directory does not exist: {resolved_path}"
        result = self.git_manager.init_repo(resolved_path)
        if result.success:
            return True, "Git repository initialized successfully."
        return False, result.error_message or "Failed to initialize Git repository."

    def add_project(
        self,
        name: str,
        path: Union[str, Path],
        mode: Union[ProjectMode, str] = ProjectMode.AUTO,
        enabled: bool = True,
        remote: str = "origin",
        remote_url: Optional[str] = None,
        branch: Optional[str] = None,
        commit_message: str = "auto: update project",
        debounce_seconds: Optional[int] = None,
    ) -> tuple[bool, str, Optional[ProjectConfig]]:
        """Registers a new project via the project manager."""
        return self.project_manager.add_project(
            name=name,
            path=path,
            mode=mode,
            enabled=enabled,
            remote=remote,
            remote_url=remote_url,
            branch=branch,
            commit_message=commit_message,
            debounce_seconds=debounce_seconds,
        )

    def remove_project(self, name: str) -> tuple[bool, str]:
        """Removes a project from management without deleting local repository files."""
        return self.project_manager.remove_project(name)

    def set_project_mode(self, name: str, mode: Union[ProjectMode, str]) -> tuple[bool, str]:
        return self.project_manager.set_project_mode(name, mode)

    def set_project_debounce(self, name: str, debounce_seconds: int) -> tuple[bool, str]:
        return self.project_manager.set_project_debounce(name, debounce_seconds)

    def set_default_debounce(self, debounce_seconds: int) -> bool:
        self.config.default_debounce_seconds = max(1, int(debounce_seconds))
        return self.config_manager.save_config(self.config)

    def set_project_enabled(self, name: str, enabled: bool) -> tuple[bool, str]:
        return self.project_manager.set_project_enabled(name, enabled)

    def get_project_state(self, project_name: str) -> Optional[ProjectRuntimeState]:
        """Queries the runtime state of a specific project."""
        with self._states_lock:
            state = self._states.get(project_name)
            if state:
                watcher = self.watcher_manager.get_watcher(project_name)
                state.is_watching = watcher.is_running if watcher else False
                state.is_timer_running = watcher.is_timer_running if watcher else False
            return state

    def get_system_status(self) -> SystemStatus:
        """Builds a comprehensive real-time status summary of all projects and engine."""
        with self._states_lock:
            runtime_states = []
            active_count = 0
            paused_count = 0
            disabled_count = 0

            for project in self.config.projects:
                state = self._states.get(project.name)
                if not state:
                    state = self._get_or_create_state(project)

                watcher = self.watcher_manager.get_watcher(project.name)
                state.is_watching = watcher.is_running if watcher else False
                state.is_timer_running = watcher.is_timer_running if watcher else False

                if not project.enabled:
                    disabled_count += 1
                elif project.mode == ProjectMode.PAUSED:
                    paused_count += 1
                else:
                    active_count += 1

                runtime_states.append(state)

            gh_status = self.github_service.get_status()
            uptime = time.time() - self._start_time if self._is_running else 0.0

            return SystemStatus(
                total_projects=len(self.config.projects),
                active_projects=active_count,
                paused_projects=paused_count,
                disabled_projects=disabled_count,
                is_online=self.network_monitor.is_online,
                github_connected=gh_status.connected,
                github_username=gh_status.username,
                uptime_seconds=uptime,
                projects=runtime_states,
            )

    def _on_network_reconnected(self) -> None:
        with self._offline_lock:
            pending_names = list(self._offline_pending_projects)
        if not pending_names:
            return

        logger.info(
            f"[NETWORK] Internet connectivity restored. Flushing offline queue for {len(pending_names)} project(s)..."
        )
        flushed_count = 0
        for name in pending_names:
            project = self.project_manager.get_project(name)
            if project and project.enabled and project.mode != ProjectMode.PAUSED:
                success = self.process_project_sync(project, manual=True)
                if success:
                    flushed_count += 1
                    with self._offline_lock:
                        self._offline_pending_projects.discard(name)

        if flushed_count > 0:
            from src.utils.notifications import send_macos_notification

            send_macos_notification(
                message=f"Conexión restablecida: {flushed_count} repositorio(s) sincronizados.",
                subtitle="Auto-Sync Completado",
            )

    def connect_github(
        self,
        username: str,
        token: Optional[str] = None,
        auth_type: str = "keychain",
    ) -> bool:
        success = self.github_service.connect(username, token=token, auth_type=auth_type)
        if success:
            self.config.github_username = username.strip()
            self.config_manager.save_config(self.config)
        return success

    def disconnect_github(self) -> bool:
        success = self.github_service.disconnect()
        self.config.github_username = None
        self.config_manager.save_config(self.config)
        return success

    def get_github_status(self) -> GitHubAuthStatus:
        return self.github_service.get_status()

    def stop(self) -> None:
        """Stops the engine and cleanly terminates all watchers."""
        if not self._is_running:
            return
        logger.info("[SYSTEM] Stopping GH-BOT-REPOS-MAC engine...")
        self.watcher_manager.stop_all()
        self.network_monitor.stop()
        self._is_running = False
        logger.info("[SYSTEM] GH-BOT-REPOS-MAC engine stopped.")

    @property
    def is_running(self) -> bool:
        return self._is_running

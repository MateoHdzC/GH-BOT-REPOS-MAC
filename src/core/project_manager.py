"""Project management layer handling CRUD operations and validation for watched Git repositories."""

from pathlib import Path
from typing import Callable, Optional, Union

from src.config.manager import ConfigManager
from src.config.models import AppConfig, ProjectConfig, ProjectMode
from src.git.git_manager import GitManager
from src.utils.constants import DEFAULT_COMMIT_MESSAGE, DEFAULT_DEBOUNCE_SECONDS, DEFAULT_REMOTE
from src.utils.logger import get_logger
from src.watcher.repo_watcher import WatcherManager

logger = get_logger("project")


class ProjectManager:
    """Manages project configurations, lifecycle, and Git validation without UI coupling."""

    def __init__(
        self,
        config_manager: ConfigManager,
        git_manager: GitManager,
        watcher_manager: WatcherManager,
        on_project_changed: Optional[Callable[[ProjectConfig], None]] = None,
        on_project_removed: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.config_manager = config_manager
        self.git_manager = git_manager
        self.watcher_manager = watcher_manager
        self.on_project_changed = on_project_changed
        self.on_project_removed = on_project_removed
        self._config: AppConfig = self.config_manager.load_config()

    def reload_config(self) -> AppConfig:
        """Reloads configuration from disk."""
        self._config = self.config_manager.load_config()
        return self._config

    @property
    def config(self) -> AppConfig:
        return self._config

    def list_projects(self) -> list[ProjectConfig]:
        """Returns all configured projects."""
        return list(self._config.projects)

    def get_project(self, name: str) -> Optional[ProjectConfig]:
        """Retrieves a project configuration by name."""
        return self._config.get_project_by_name(name)

    def add_project(
        self,
        name: str,
        path: Union[str, Path],
        mode: Union[ProjectMode, str] = ProjectMode.AUTO,
        enabled: bool = True,
        remote: str = DEFAULT_REMOTE,
        remote_url: Optional[str] = None,
        branch: Optional[str] = None,
        commit_message: str = DEFAULT_COMMIT_MESSAGE,
        debounce_seconds: Optional[int] = None,
    ) -> tuple[bool, str, Optional[ProjectConfig]]:
        """Validates and registers a new project.

        Validation Steps:
            1. Path existence and directory type.
            2. Valid Git repository inspection.
            3. Remote URL configuration if provided.
            4. Duplicate verification by name and canonical path.

        Returns:
            (success: bool, message: str, project: Optional[ProjectConfig])
        """
        clean_name = (name or "").strip()
        if not clean_name:
            msg = "Project name cannot be empty."
            logger.error(f"[PROJECT] [ERROR] {msg}")
            return False, msg, None

        raw_path = Path(path)
        resolved_path = raw_path.expanduser().resolve()

        # 1. Validate path exists
        if not resolved_path.exists():
            msg = f"Directory does not exist: {resolved_path}"
            logger.error(f"[PROJECT] [ERROR] [{clean_name}] {msg}")
            return False, msg, None

        # 2. Validate is a directory
        if not resolved_path.is_dir():
            msg = f"Specified path is not a directory: {resolved_path}"
            logger.error(f"[PROJECT] [ERROR] [{clean_name}] {msg}")
            return False, msg, None

        # 3. Validate is a Git repository
        if not self.git_manager.is_git_repo(resolved_path):
            msg = f"Path is not a valid Git repository: {resolved_path}"
            logger.error(f"[PROJECT] [ERROR] [{clean_name}] {msg}")
            return False, msg, None

        # 4. If a remote URL is specified, configure or update Git remote
        remote_name = remote.strip() or DEFAULT_REMOTE
        if remote_url and remote_url.strip():
            rem_res = self.git_manager.set_remote_url(resolved_path, remote_url.strip(), remote_name=remote_name)
            if not rem_res.success:
                logger.warning(f"[PROJECT] Warning setting remote '{remote_name}' to '{remote_url}': {rem_res.error_message}")

        # 5. Check for duplicates by canonical path
        if self._config.get_project_by_path(resolved_path) is not None:
            msg = f"A project pointing to directory '{resolved_path}' is already registered."
            logger.warning(f"[PROJECT] [ERROR] {msg}")
            return False, msg, None

        # 6. Handle duplicate name by auto-disambiguating
        final_name = clean_name
        counter = 2
        while self._config.get_project_by_name(final_name) is not None:
            final_name = f"{clean_name} ({counter})"
            counter += 1

        # Parse mode
        parsed_mode = (
            mode if isinstance(mode, ProjectMode) else ProjectMode.from_string(str(mode))
        )
        actual_debounce = (
            debounce_seconds
            if debounce_seconds is not None
            else self._config.default_debounce_seconds
        )
        detected_branch = branch or self.git_manager.get_current_branch(resolved_path)

        new_project = ProjectConfig(
            name=final_name,
            path=raw_path,
            enabled=enabled,
            mode=parsed_mode,
            branch=detected_branch,
            remote=remote_name,
            commit_message=commit_message.strip() or DEFAULT_COMMIT_MESSAGE,
            debounce_seconds=max(1, actual_debounce),
        )

        updated_projects = list(self._config.projects) + [new_project]
        self._config.projects = updated_projects

        if not self.config_manager.save_config(self._config):
            msg = "Failed to persist updated configuration to disk."
            logger.error(f"[PROJECT] [ERROR] [{clean_name}] {msg}")
            return False, msg, None

        # Start watcher if project is enabled
        self.watcher_manager.add_or_update_watcher(new_project)
        if self.on_project_changed:
            self.on_project_changed(new_project)

        logger.info(
            f"[PROJECT] Project '{clean_name}' added successfully on {resolved_path} (Mode: {parsed_mode.value}, Branch: {detected_branch or 'default'})"
        )
        return True, "Project added successfully.", new_project

    def remove_project(self, name: str) -> tuple[bool, str]:
        """Unregisters a project from GH-BOT-REPOS-MAC without deleting local files.

        Stops its watcher, cancels timers, and removes entry from config.
        """
        project = self.get_project(name)
        if not project:
            msg = f"Project '{name}' was not found."
            logger.warning(f"[PROJECT] [ERROR] {msg}")
            return False, msg

        # Stop watcher and cancel pending timers
        self.watcher_manager.remove_watcher(name)

        # Remove from configuration list
        self._config.projects = [p for p in self._config.projects if p.name != name]
        self.config_manager.save_config(self._config)

        if self.on_project_removed:
            self.on_project_removed(name)

        logger.info(
            f"[PROJECT] Project '{name}' removed from manager. Local repository files remain untouched."
        )
        return True, f"Project '{name}' removed successfully."

    def set_project_mode(
        self, name: str, mode: Union[ProjectMode, str]
    ) -> tuple[bool, str]:
        """Updates the operational mode (AUTO, COMMIT_ONLY, PAUSED) of a project."""
        project = self.get_project(name)
        if not project:
            msg = f"Project '{name}' was not found."
            logger.warning(f"[PROJECT] [ERROR] {msg}")
            return False, msg

        parsed_mode = (
            mode if isinstance(mode, ProjectMode) else ProjectMode.from_string(str(mode))
        )
        if parsed_mode.value not in [m.value for m in ProjectMode]:
            msg = f"Invalid mode '{mode}'. Allowed modes: AUTO, COMMIT_ONLY, PAUSED."
            logger.error(f"[PROJECT] [ERROR] {msg}")
            return False, msg

        updated_project = ProjectConfig(
            name=project.name,
            path=project.path,
            enabled=project.enabled,
            mode=parsed_mode,
            branch=project.branch,
            remote=project.remote,
            commit_message=project.commit_message,
            debounce_seconds=project.debounce_seconds,
        )

        self._update_in_list(updated_project)
        self.config_manager.save_config(self._config)
        self.watcher_manager.add_or_update_watcher(updated_project)

        if self.on_project_changed:
            self.on_project_changed(updated_project)

        logger.info(f"[PROJECT] Project '{name}' mode changed to {parsed_mode.value}.")
        return True, f"Project '{name}' mode changed to {parsed_mode.value}."

    def set_project_enabled(self, name: str, enabled: bool) -> tuple[bool, str]:
        """Toggles active monitoring status for a specific project."""
        project = self.get_project(name)
        if not project:
            msg = f"Project '{name}' was not found."
            logger.warning(f"[PROJECT] [ERROR] {msg}")
            return False, msg

        updated_project = ProjectConfig(
            name=project.name,
            path=project.path,
            enabled=enabled,
            mode=project.mode,
            branch=project.branch,
            remote=project.remote,
            commit_message=project.commit_message,
            debounce_seconds=project.debounce_seconds,
        )

        self._update_in_list(updated_project)
        self.config_manager.save_config(self._config)
        self.watcher_manager.add_or_update_watcher(updated_project)

        if self.on_project_changed:
            self.on_project_changed(updated_project)

        state_label = "enabled" if enabled else "disabled"
        logger.info(f"[PROJECT] Project '{name}' is now {state_label}.")
        return True, f"Project '{name}' is now {state_label}."

    def update_project(
        self,
        name: str,
        commit_message: Optional[str] = None,
        remote: Optional[str] = None,
        branch: Optional[str] = None,
        debounce_seconds: Optional[int] = None,
    ) -> tuple[bool, str]:
        """Updates specific configuration parameters for an existing project."""
        project = self.get_project(name)
        if not project:
            msg = f"Project '{name}' was not found."
            return False, msg

        updated_project = ProjectConfig(
            name=project.name,
            path=project.path,
            enabled=project.enabled,
            mode=project.mode,
            branch=branch if branch is not None else project.branch,
            remote=remote.strip() if remote else project.remote,
            commit_message=commit_message.strip() if commit_message else project.commit_message,
            debounce_seconds=debounce_seconds if debounce_seconds is not None else project.debounce_seconds,
        )

        self._update_in_list(updated_project)
        self.config_manager.save_config(self._config)
        self.watcher_manager.add_or_update_watcher(updated_project)

        if self.on_project_changed:
            self.on_project_changed(updated_project)

        logger.info(f"[PROJECT] Project '{name}' configuration updated.")
        return True, f"Project '{name}' updated successfully."

    def _update_in_list(self, project: ProjectConfig) -> None:
        new_list = []
        for p in self._config.projects:
            if p.name == project.name:
                new_list.append(project)
            else:
                new_list.append(p)
        self._config.projects = new_list

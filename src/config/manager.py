"""Configuration manager for loading and validating project definitions."""

import json
from pathlib import Path
from typing import Any, Optional

from src.config.models import AppConfig, ProjectConfig, ProjectMode
from src.utils.constants import DEFAULT_CONFIG_PATH, DEFAULT_DEBOUNCE_SECONDS
from src.utils.logger import get_logger

logger = get_logger("config")


class ConfigManager:
    """Handles loading, validating, and persisting project configurations."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self.config_path = config_path or DEFAULT_CONFIG_PATH

    def load_config(self) -> AppConfig:
        """Loads and parses the configuration file.

        Returns an AppConfig instance. If the file is missing or invalid,
        returns a default configuration and logs appropriate warnings.
        """
        if not self.config_path.exists():
            logger.warning(
                f"[PROJECT] Configuration file not found at {self.config_path}. Using empty configuration."
            )
            return AppConfig()

        try:
            with open(self.config_path, "r", encoding="utf-8") as file:
                raw_data = json.load(file)
            return self._parse_config_dict(raw_data)
        except json.JSONDecodeError as err:
            logger.error(
                f"[PROJECT] [ERROR] Invalid JSON syntax in configuration file {self.config_path}: {err}. Returning empty config."
            )
            return AppConfig()
        except OSError as err:
            logger.error(
                f"[PROJECT] [ERROR] Failed to read configuration file {self.config_path}: {err}. Returning empty config."
            )
            return AppConfig()

    def _parse_config_dict(self, data: dict[str, Any]) -> AppConfig:
        """Parses and validates raw dictionary data into typed AppConfig."""
        if not isinstance(data, dict):
            logger.error("[PROJECT] [ERROR] Configuration root must be a JSON object.")
            return AppConfig()

        global_debounce = int(
            data.get("default_debounce_seconds", DEFAULT_DEBOUNCE_SECONDS)
        )
        raw_projects = data.get("projects", [])

        if not isinstance(raw_projects, list):
            logger.error("[PROJECT] [ERROR] 'projects' field must be a list.")
            return AppConfig(default_debounce_seconds=global_debounce)

        parsed_projects: list[ProjectConfig] = []
        for idx, item in enumerate(raw_projects):
            if not isinstance(item, dict):
                logger.warning(f"[PROJECT] Skipping invalid project entry at index {idx}: not a dict.")
                continue

            name = item.get("name")
            path_str = item.get("path")

            if not name or not isinstance(name, str):
                logger.warning(f"[PROJECT] Skipping project at index {idx}: missing or invalid 'name'.")
                continue

            if not path_str or not isinstance(path_str, str):
                logger.warning(
                    f"[PROJECT] Skipping project '{name}': missing or invalid 'path'."
                )
                continue

            mode_str = item.get("mode", "AUTO")
            mode = ProjectMode.from_string(str(mode_str))

            project = ProjectConfig(
                name=name.strip(),
                path=Path(path_str),
                enabled=bool(item.get("enabled", True)),
                mode=mode,
                branch=item.get("branch"),
                remote=str(item.get("remote", "origin")),
                commit_message=str(
                    item.get("commit_message", "auto: update project")
                ),
                debounce_seconds=int(
                    item.get("debounce_seconds", global_debounce)
                ),
            )
            parsed_projects.append(project)

        logger.info(f"[PROJECT] Loaded {len(parsed_projects)} project(s) from {self.config_path}")
        return AppConfig(
            projects=parsed_projects,
            default_debounce_seconds=global_debounce,
            github_username=data.get("github_username"),
        )

    def save_config(self, config: AppConfig) -> bool:
        """Serializes and saves the AppConfig instance to the configured JSON path."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "default_debounce_seconds": config.default_debounce_seconds,
                "github_username": config.github_username,
                "projects": [
                    {
                        "name": p.name,
                        "path": str(p.path),
                        "enabled": p.enabled,
                        "mode": p.mode.value,
                        "branch": p.branch,
                        "remote": p.remote,
                        "commit_message": p.commit_message,
                        "debounce_seconds": p.debounce_seconds,
                    }
                    for p in config.projects
                ],
            }
            with open(self.config_path, "w", encoding="utf-8") as file:
                json.dump(payload, file, indent=2, ensure_ascii=False)
            logger.info(f"[PROJECT] Configuration saved successfully to {self.config_path}")
            return True
        except OSError as err:
            logger.error(f"[PROJECT] [ERROR] Failed to save configuration to {self.config_path}: {err}")
            return False

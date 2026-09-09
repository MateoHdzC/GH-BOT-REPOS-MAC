"""Data models for application and project configurations."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from src.utils.constants import (
    DEFAULT_COMMIT_MESSAGE,
    DEFAULT_DEBOUNCE_SECONDS,
    DEFAULT_REMOTE,
)


class ProjectMode(str, Enum):
    """Operational mode defining automated behavior for a repository."""

    AUTO = "AUTO"
    COMMIT_ONLY = "COMMIT_ONLY"
    PAUSED = "PAUSED"

    @classmethod
    def from_string(cls, value: str) -> "ProjectMode":
        """Parses a string into a valid ProjectMode, defaulting to AUTO on unrecognized values."""
        normalized = (value or "").strip().upper()
        for mode in cls:
            if mode.value == normalized:
                return mode
        return cls.AUTO


@dataclass(frozen=True)
class ProjectConfig:
    """Configuration for a single watched Git project."""

    name: str
    path: Path
    enabled: bool = True
    mode: ProjectMode = ProjectMode.AUTO
    branch: Optional[str] = None
    remote: str = DEFAULT_REMOTE
    commit_message: str = DEFAULT_COMMIT_MESSAGE
    debounce_seconds: int = DEFAULT_DEBOUNCE_SECONDS

    def resolved_path(self) -> Path:
        """Returns the absolute resolved path with expanded user home."""
        return self.path.expanduser().resolve()


@dataclass
class AppConfig:
    """Root configuration holding all watched projects and global settings."""

    projects: list[ProjectConfig] = field(default_factory=list)
    default_debounce_seconds: int = DEFAULT_DEBOUNCE_SECONDS
    github_username: Optional[str] = None

    def get_enabled_projects(self) -> list[ProjectConfig]:
        """Returns only enabled project configurations."""
        return [p for p in self.projects if p.enabled]

    def get_project_by_name(self, name: str) -> Optional[ProjectConfig]:
        """Finds a project configuration by its unique name."""
        for p in self.projects:
            if p.name == name:
                return p
        return None

    def get_project_by_path(self, path: Path) -> Optional[ProjectConfig]:
        """Finds a project configuration by its canonical directory path."""
        resolved = path.expanduser().resolve()
        for p in self.projects:
            if p.resolved_path() == resolved:
                return p
        return None

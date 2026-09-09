"""Runtime state representation and query models for GH-BOT-REPOS-MAC."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from src.config.models import ProjectMode


class SyncStatus(str, Enum):
    """Status of the most recent Git synchronization execution."""

    IDLE = "IDLE"
    SYNCING = "SYNCING"
    SUCCESS = "SUCCESS"
    NO_CHANGES = "NO_CHANGES"
    STAGING_FAILED = "STAGING_FAILED"
    COMMIT_FAILED = "COMMIT_FAILED"
    PUSH_FAILED = "PUSH_FAILED"
    OFFLINE_QUEUED = "OFFLINE_QUEUED"
    SKIPPED_PAUSED = "SKIPPED_PAUSED"
    ERROR = "ERROR"


@dataclass
class ProjectRuntimeState:
    """Dynamic runtime state of a managed repository."""

    name: str
    path: str
    mode: ProjectMode = ProjectMode.AUTO
    enabled: bool = True
    is_watching: bool = False
    is_timer_running: bool = False
    is_offline_queued: bool = False
    current_branch: Optional[str] = None
    last_change_detected_at: Optional[str] = None
    last_commit_at: Optional[str] = None
    last_commit_hash: Optional[str] = None
    last_commit_message: Optional[str] = None
    last_push_at: Optional[str] = None
    last_sync_status: SyncStatus = SyncStatus.IDLE
    debounce_seconds: int = 300
    last_error: Optional[str] = None
    last_error_type: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "mode": self.mode.value,
            "enabled": self.enabled,
            "debounce_seconds": self.debounce_seconds,
            "is_watching": self.is_watching,
            "is_timer_running": self.is_timer_running,
            "is_offline_queued": self.is_offline_queued,
            "current_branch": self.current_branch,
            "last_change_detected_at": self.last_change_detected_at,
            "last_commit_at": self.last_commit_at,
            "last_commit_hash": self.last_commit_hash,
            "last_commit_message": self.last_commit_message,
            "last_push_at": self.last_push_at,
            "last_sync_status": self.last_sync_status.value,
            "last_error": self.last_error,
            "last_error_type": self.last_error_type,
        }


@dataclass
class SystemStatus:
    """Global system status snapshot for the whole daemon engine."""

    total_projects: int = 0
    active_projects: int = 0
    paused_projects: int = 0
    disabled_projects: int = 0
    is_online: bool = True
    github_connected: bool = False
    github_username: Optional[str] = None
    uptime_seconds: float = 0.0
    projects: list[ProjectRuntimeState] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serializes the system status for UI consumers."""
        return {
            "total_projects": self.total_projects,
            "active_projects": self.active_projects,
            "paused_projects": self.paused_projects,
            "disabled_projects": self.disabled_projects,
            "is_online": self.is_online,
            "github_connected": self.github_connected,
            "github_username": self.github_username,
            "uptime_seconds": round(self.uptime_seconds, 2),
            "projects": [p.to_dict() for p in self.projects],
        }

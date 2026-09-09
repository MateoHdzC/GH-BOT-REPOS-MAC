"""Data models representing Git command outcomes, classifications, and status summaries."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class GitErrorType(str, Enum):
    """Categorized Git failure classifications for clear operational feedback."""

    NO_REMOTE = "NO_REMOTE"
    REMOTE_NOT_FOUND = "REMOTE_NOT_FOUND"
    AUTH_FAILED = "AUTH_FAILED"
    NETWORK_ERROR = "NETWORK_ERROR"
    REJECTED_NON_FAST_FORWARD = "REJECTED_NON_FAST_FORWARD"
    CONFLICT = "CONFLICT"
    BRANCH_NOT_FOUND = "BRANCH_NOT_FOUND"
    LOCAL_REPO_INVALID = "LOCAL_REPO_INVALID"
    COMMAND_TIMEOUT = "COMMAND_TIMEOUT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class CommitInfo:
    """Metadata of a specific Git commit."""

    hash: str
    message: str
    author: str
    timestamp: str


@dataclass(frozen=True)
class GitCommandResult:
    """Result of an executed Git CLI command."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    error_message: Optional[str] = None
    error_type: Optional[GitErrorType] = None


@dataclass(frozen=True)
class GitStatusSummary:
    """Parsed high-level summary of a Git repository status."""

    is_git_repo: bool
    has_changes: bool = False
    staged_files_count: int = 0
    unstaged_files_count: int = 0
    untracked_files_count: int = 0
    current_branch: Optional[str] = None
    remotes: tuple[str, ...] = ()
    raw_status: str = ""

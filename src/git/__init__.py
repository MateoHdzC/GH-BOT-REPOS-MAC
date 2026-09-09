"""Git integration layer for GH-BOT-REPOS-MAC."""

from src.git.git_manager import GitManager
from src.git.models import GitCommandResult, GitStatusSummary

__all__ = ["GitCommandResult", "GitManager", "GitStatusSummary"]

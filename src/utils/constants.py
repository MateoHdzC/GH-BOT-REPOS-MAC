"""Global constants and defaults for GH-BOT-REPOS-MAC."""

from pathlib import Path

DEFAULT_DEBOUNCE_SECONDS: int = 300
DEFAULT_COMMIT_MESSAGE: str = "auto: update project"
DEFAULT_REMOTE: str = "origin"
DEFAULT_CONFIG_PATH: Path = Path("config/projects.json")
DEFAULT_LOG_PATH: Path = Path("logs/app.log")
DEFAULT_LOCK_PATH: Path = Path.home() / ".gh_bot_mac.lock"

IGNORED_DIR_NAMES: set[str] = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".idea",
    ".vscode",
    "node_modules",
    "logs",
    ".pytest_cache",
    ".tox",
    ".nox",
    "build",
    "dist",
}

IGNORED_FILE_PATTERNS: set[str] = {
    ".DS_Store",
    ".AppleDouble",
    ".LSOverride",
    ".env*",
    "*.env*",
    "*.pem",
    "*.key",
    "*.cert",
    "*.crt",
    "secrets*",
    "credentials*",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.swp",
    "*.swo",
    "*~",
}

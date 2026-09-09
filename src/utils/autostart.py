"""Official macOS LaunchAgents manager for configuring auto-start on login."""

import plistlib
import sys
from pathlib import Path
from typing import Optional

from src.utils.logger import get_logger

logger = get_logger("autostart")

DEFAULT_PLIST_NAME = "com.mateohdz.ghbotmac.plist"
DEFAULT_LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"


def get_default_plist_path() -> Path:
    """Returns the default LaunchAgent plist path for the current user."""
    return DEFAULT_LAUNCH_AGENTS_DIR / DEFAULT_PLIST_NAME


def is_autostart_enabled(plist_path: Optional[Path] = None) -> bool:
    """Checks if the LaunchAgent plist file exists and is active."""
    target = plist_path or get_default_plist_path()
    return target.exists()


def enable_autostart(
    app_root: Optional[Path] = None,
    plist_path: Optional[Path] = None,
    python_exec: Optional[str] = None,
) -> bool:
    """Creates and installs the official macOS LaunchAgent plist.

    Runs GH-BOT-REPOS-MAC with --background on user login without opening a terminal or window.
    """
    target_plist = plist_path or get_default_plist_path()
    root_dir = (app_root or Path(__file__).resolve().parent.parent.parent).resolve()
    py_bin = python_exec or sys.executable
    log_file = root_dir / "logs" / "autostart.log"

    plist_data = {
        "Label": "com.mateohdz.ghbotmac",
        "ProgramArguments": [
            py_bin,
            "-m",
            "src.ui.app",
            "--background",
        ],
        "WorkingDirectory": str(root_dir),
        "RunAtLoad": True,
        "KeepAlive": False,
        "StandardOutPath": str(log_file),
        "StandardErrorPath": str(log_file),
        "ProcessType": "Interactive",
    }

    try:
        target_plist.parent.mkdir(parents=True, exist_ok=True)
        with open(target_plist, "wb") as f:
            plistlib.dump(plist_data, f)
        logger.info(f"[SYSTEM] Auto-start LaunchAgent enabled at {target_plist}")
        return True
    except Exception as err:
        logger.error(f"[SYSTEM] [ERROR] Failed to write LaunchAgent plist: {err}")
        return False


def disable_autostart(plist_path: Optional[Path] = None) -> bool:
    """Removes the LaunchAgent plist to disable automatic startup."""
    target_plist = plist_path or get_default_plist_path()
    try:
        if target_plist.exists():
            target_plist.unlink()
            logger.info(f"[SYSTEM] Auto-start LaunchAgent removed from {target_plist}")
        return True
    except Exception as err:
        logger.error(f"[SYSTEM] [ERROR] Failed to remove LaunchAgent plist: {err}")
        return False

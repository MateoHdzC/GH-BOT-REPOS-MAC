"""Native macOS user notification dispatcher using AppleScript / NotificationCenter."""

import subprocess
from typing import Optional

from src.utils.logger import get_logger

logger = get_logger("notifications")


def send_macos_notification(
    message: str,
    title: str = "GH-BOT-REPOS-MAC",
    subtitle: Optional[str] = None,
    sound: bool = False,
) -> bool:
    """Sends a native macOS desktop notification via AppleScript.

    Used strictly for important events (push completed, push failed, critical error).
    """
    clean_msg = message.replace('"', '\\"').replace("'", "'")
    clean_title = title.replace('"', '\\"')

    script_parts = [f'display notification "{clean_msg}" with title "{clean_title}"']
    if subtitle:
        clean_subtitle = subtitle.replace('"', '\\"')
        script_parts.append(f'subtitle "{clean_subtitle}"')
    if sound:
        script_parts.append('sound name "Default"')

    script = " ".join(script_parts)
    cmd = ["/usr/bin/osascript", "-e", script]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=5)
        if res.returncode == 0:
            logger.debug(f"[NOTIFICATIONS] Notification sent: '{message}'")
            return True
        logger.warning(f"[NOTIFICATIONS] [ERROR] osascript failed: {res.stderr.strip()}")
        return False
    except Exception as err:
        logger.warning(f"[NOTIFICATIONS] [ERROR] Could not send notification: {err}")
        return False

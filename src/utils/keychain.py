"""macOS Keychain security helper for storing and retrieving sensitive tokens."""

import subprocess
from typing import Optional

from src.utils.logger import get_logger

logger = get_logger("keychain")

SERVICE_NAME = "com.mateohdz.ghbotmac.github"


class KeychainManager:
    """Safely interfaces with macOS native security CLI for credential storage."""

    @staticmethod
    def save_credential(account: str, secret: str, service: str = SERVICE_NAME) -> bool:
        """Saves or updates a generic password item in the macOS Keychain."""
        if not account or not secret:
            return False

        # First delete any existing item to ensure clean update
        KeychainManager.delete_credential(account, service)

        cmd = [
            "/usr/bin/security",
            "add-generic-password",
            "-a",
            account,
            "-s",
            service,
            "-w",
            secret,
            "-U",  # Update if exists
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                logger.info(f"[SYSTEM] Secure credential stored in Keychain for account '{account}'.")
                return True
            logger.warning(f"[SYSTEM] [ERROR] Failed to save credential in Keychain: {res.stderr.strip()}")
            return False
        except Exception as err:
            logger.error(f"[SYSTEM] [ERROR] Keychain save error: {err}")
            return False

    @staticmethod
    def get_credential(account: str, service: str = SERVICE_NAME) -> Optional[str]:
        """Retrieves a generic password item from the macOS Keychain."""
        if not account:
            return None

        cmd = [
            "/usr/bin/security",
            "find-generic-password",
            "-a",
            account,
            "-s",
            service,
            "-w",  # Output password only
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0 and res.stdout:
                return res.stdout.strip()
            return None
        except Exception as err:
            logger.error(f"[SYSTEM] [ERROR] Keychain read error: {err}")
            return None

    @staticmethod
    def delete_credential(account: str, service: str = SERVICE_NAME) -> bool:
        """Deletes a generic password item from the macOS Keychain."""
        if not account:
            return False

        cmd = [
            "/usr/bin/security",
            "delete-generic-password",
            "-a",
            account,
            "-s",
            service,
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            return res.returncode == 0
        except Exception as err:
            logger.error(f"[SYSTEM] [ERROR] Keychain delete error: {err}")
            return False

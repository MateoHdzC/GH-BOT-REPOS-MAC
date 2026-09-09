"""macOS Keychain security helper with secure local storage fallback."""

import json
import os
import subprocess
from pathlib import Path
from typing import Optional

from src.utils.constants import DEFAULT_CONFIG_PATH
from src.utils.logger import get_logger

logger = get_logger("keychain")

SERVICE_NAME = "com.mateohdz.ghbotmac.github"
SECRETS_FILE = DEFAULT_CONFIG_PATH.parent / ".secrets.json"


class KeychainManager:
    """Safely interfaces with macOS Keychain and restricted user-only local secrets."""

    @staticmethod
    def _save_local_secret(account: str, secret: str) -> bool:
        try:
            SECRETS_FILE.parent.mkdir(parents=True, exist_ok=True)
            existing = {}
            if SECRETS_FILE.exists():
                try:
                    existing = json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
                except Exception:
                    existing = {}
            existing[account] = secret
            SECRETS_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")
            os.chmod(SECRETS_FILE, 0o600)  # Restricted user-only permissions
            return True
        except Exception as err:
            logger.error(f"[SYSTEM] [ERROR] Failed to save local secrets: {err}")
            return False

    @staticmethod
    def _get_local_secret(account: str) -> Optional[str]:
        try:
            if SECRETS_FILE.exists():
                data = json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
                return data.get(account)
        except Exception as err:
            logger.error(f"[SYSTEM] [ERROR] Failed to read local secrets: {err}")
        return None

    @staticmethod
    def _delete_local_secret(account: str) -> bool:
        try:
            if SECRETS_FILE.exists():
                data = json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
                if account in data:
                    del data[account]
                    SECRETS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return True
        except Exception:
            return False

    @staticmethod
    def save_credential(account: str, secret: str, service: str = SERVICE_NAME) -> bool:
        """Saves or updates a generic password item in macOS Keychain or local secrets."""
        if not account or not secret:
            return False

        # 1. Remove old Keychain item if exists
        cmd_del = [
            "/usr/bin/security",
            "delete-generic-password",
            "-a",
            account,
            "-s",
            service,
        ]
        try:
            subprocess.run(cmd_del, capture_output=True, text=True, check=False)
        except Exception:
            pass

        # 2. Save to restricted local secrets file
        local_saved = KeychainManager._save_local_secret(account, secret)

        # 3. Add to macOS Keychain
        cmd = [
            "/usr/bin/security",
            "add-generic-password",
            "-a",
            account,
            "-s",
            service,
            "-w",
            secret,
            "-U",
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                logger.info(f"[SYSTEM] Secure credential stored in Keychain for account '{account}'.")
                return True
        except Exception as err:
            logger.debug(f"[SYSTEM] Keychain CLI error: {err}")

        return local_saved

    @staticmethod
    def get_credential(account: str, service: str = SERVICE_NAME) -> Optional[str]:
        """Retrieves a credential from the macOS Keychain or local secrets store."""
        if not account:
            return None

        # 1. Try Keychain first
        cmd = [
            "/usr/bin/security",
            "find-generic-password",
            "-a",
            account,
            "-s",
            service,
            "-w",
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0 and res.stdout and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass

        # 2. Fallback to private local secrets file
        return KeychainManager._get_local_secret(account)

    @staticmethod
    def delete_credential(account: str, service: str = SERVICE_NAME) -> bool:
        """Deletes a generic password item from Keychain and local secrets store."""
        if not account:
            return False

        KeychainManager._delete_local_secret(account)
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
        except Exception:
            return True

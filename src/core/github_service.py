"""GitHub authentication and connection service using macOS Keychain security."""

from dataclasses import dataclass
from typing import Optional

from src.utils.keychain import KeychainManager
from src.utils.logger import get_logger

logger = get_logger("github")


@dataclass(frozen=True)
class GitHubAuthStatus:
    """Status summary of GitHub account connection."""

    connected: bool
    username: Optional[str] = None
    auth_type: Optional[str] = None
    error_message: Optional[str] = None


class GitHubAuthService:
    """Abstracts GitHub authentication and token management without exposing raw secrets."""

    def __init__(self) -> None:
        self._connected: bool = False
        self._username: Optional[str] = None
        self._auth_type: Optional[str] = None

    def is_connected(self) -> bool:
        """Checks if a valid GitHub connection is currently established."""
        return self._connected

    def get_status(self) -> GitHubAuthStatus:
        """Returns the current connection status of the GitHub service."""
        return GitHubAuthStatus(
            connected=self._connected,
            username=self._username,
            auth_type=self._auth_type,
        )

    def connect(
        self,
        username: str,
        token: Optional[str] = None,
        auth_type: str = "keychain",
    ) -> bool:
        """Connects GitHub account and persists token to macOS Keychain securely.

        Raw tokens are never logged or stored in plaintext configuration files.
        """
        clean_user = (username or "").strip()
        if not clean_user:
            logger.error("[SYSTEM] [ERROR] Cannot connect GitHub: empty username provided.")
            return False

        if token and token.strip():
            # Store in macOS Keychain securely
            KeychainManager.save_credential(account=clean_user, secret=token.strip())

        self._connected = True
        self._username = clean_user
        self._auth_type = auth_type
        logger.info(f"[SYSTEM] GitHub connected for user '{self._username}' (via {auth_type}).")
        return True

    def disconnect(self) -> bool:
        """Disconnects the active GitHub session and removes token from Keychain."""
        if not self._connected:
            logger.info("[SYSTEM] GitHub session is already disconnected.")
            return True

        old_user = self._username
        if old_user:
            KeychainManager.delete_credential(old_user)

        self._connected = False
        self._username = None
        self._auth_type = None
        logger.info(f"[SYSTEM] GitHub session disconnected for user '{old_user}'.")
        return True

    def get_username(self) -> Optional[str]:
        """Returns the active GitHub username if connected."""
        return self._username

    def get_token(self) -> Optional[str]:
        """Retrieves the stored token from macOS Keychain for the active GitHub user."""
        if self._username:
            return KeychainManager.get_credential(self._username)
        return None

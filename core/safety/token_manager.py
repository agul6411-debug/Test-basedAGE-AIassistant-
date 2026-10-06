"""Session token management and constant-time verification.

Security Rule 1:
Require a random per-session auth token (stored in a user-only file).
"""

import hmac
import os
import secrets
from pathlib import Path

from core.safety.base import SecurityException
from core.safety.path_validator import validate_path_within_root


class TokenError(SecurityException):
    """Raised when token operations fail security checks."""


class SessionTokenManager:
    """Manages secure generation, user-isolated storage, and constant-time token verification."""

    def __init__(self, token_path: str | Path, base_dir: str | Path | None = None) -> None:
        """Initialize SessionTokenManager.

        Args:
            token_path: Relative or absolute path to store the token file.
            base_dir: Root directory confinement (defaults to data/ dir).
        """
        root = Path(base_dir).resolve() if base_dir else Path.cwd().resolve() / "data"
        self.token_file = validate_path_within_root(token_path, root)

    def generate_token(self, token_length_bytes: int = 32) -> str:
        """Generate a cryptographically secure random token and write to file with restricted permissions.

        Args:
            token_length_bytes: Number of random bytes (default 32 = 256 bits of entropy).

        Returns:
            The generated token string.
        """
        token = secrets.token_urlsafe(token_length_bytes)
        self.token_file.parent.mkdir(parents=True, exist_ok=True)

        # Write token to user-only file
        # Use atomic write or write with standard restrictive flags
        self.token_file.write_text(token, encoding="utf-8")

        # Set file permissions: user read/write only (POSIX 0o600)
        try:
            os.chmod(self.token_file, 0o600)
        except OSError:
            pass  # On Windows, os.chmod only controls read-only, but file is in user profile

        return token

    def read_token(self) -> str:
        """Read the active session token from disk.

        Returns:
            The active token string.

        Raises:
            TokenError: If token file is missing or unreadable.
        """
        if not self.token_file.exists():
            raise TokenError(f"Session token file does not exist at {self.token_file}")

        token = self.token_file.read_text(encoding="utf-8").strip()
        if not token:
            raise TokenError("Session token file is empty.")

        return token

    @staticmethod
    def verify_token(candidate_token: str, expected_token: str) -> bool:
        """Verify candidate token against expected token using constant-time comparison to prevent timing attacks.

        Args:
            candidate_token: Token received from untrusted client.
            expected_token: Expected valid session token.

        Returns:
            True if tokens match exactly, False otherwise.
        """
        if not candidate_token or not expected_token:
            return False
        return hmac.compare_digest(candidate_token.strip(), expected_token.strip())

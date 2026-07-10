"""Password hashing service with bcrypt-compatible backends."""

from __future__ import annotations


class PasswordHasher:
    """Hash and verify passwords for authentication services."""

    def __init__(self) -> None:
        self._passlib_context = self._load_passlib_context()
        self._bcrypt_module = self._load_bcrypt_module()

    @staticmethod
    def _load_passlib_context():
        try:
            from passlib.context import CryptContext
        except ImportError:
            return None
        return CryptContext(schemes=["bcrypt"], deprecated="auto")

    @staticmethod
    def _load_bcrypt_module():
        try:
            import bcrypt
        except ImportError:
            return None
        return bcrypt

    def hash_password(self, password: str) -> str:
        """Hash a raw password with bcrypt.

        Args:
            password: Plain-text password.

        Returns:
            A bcrypt-compatible password hash string.

        Raises:
            ValueError: If password is empty.
            RuntimeError: If no bcrypt backend is installed.
        """
        if not password:
            raise ValueError("Password cannot be empty")

        if self._passlib_context is not None:
            return str(self._passlib_context.hash(password))

        if self._bcrypt_module is not None:
            hashed = self._bcrypt_module.hashpw(
                password.encode("utf-8"),
                self._bcrypt_module.gensalt(),
            )
            return hashed.decode("utf-8")

        raise RuntimeError("Password hashing backend not available (passlib/bcrypt)")

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a raw password against a hash.

        Args:
            password: Plain-text password candidate.
            password_hash: Stored bcrypt-compatible hash.

        Returns:
            True when the password matches, otherwise False.
        """
        if not password or not password_hash:
            return False

        if self._passlib_context is not None:
            return bool(self._passlib_context.verify(password, password_hash))

        if self._bcrypt_module is not None:
            try:
                return bool(
                    self._bcrypt_module.checkpw(
                        password.encode("utf-8"),
                        password_hash.encode("utf-8"),
                    )
                )
            except ValueError:
                return False

        raise RuntimeError(
            "Password verification backend not available (passlib/bcrypt)"
        )

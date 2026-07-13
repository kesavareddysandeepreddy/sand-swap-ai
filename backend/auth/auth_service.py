"""Authentication service foundation without API handlers."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import requests

from backend.auth.password_hasher import PasswordHasher
from backend.auth.token_service import TokenService
from backend.config.config_manager import ConfigManager
from backend.domain.entities.user import User
from backend.services.user_service import UserService


@dataclass(slots=True)
class AuthService:
    """Application service for user registration and authentication."""

    user_service: UserService
    password_hasher: PasswordHasher
    token_service: TokenService = field(default_factory=TokenService)
    _password_hashes: dict[str, str] = field(default_factory=dict)

    def _google_client_id(self) -> str:
        """Resolve Google OAuth client id from env/config."""
        env_value = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
        if env_value:
            return env_value
        config_value = str(ConfigManager().get("auth.google_client_id", "")).strip()
        return config_value

    def _google_client_secret(self) -> str:
        """Resolve Google OAuth client secret from env/config."""
        env_value = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
        if env_value:
            return env_value
        config_value = str(ConfigManager().get("auth.google_client_secret", "")).strip()
        return config_value

    def build_google_authorization_url(
        self,
        *,
        redirect_uri: str,
        state: str,
    ) -> str:
        """Build the Google OAuth2 authorization URL for login."""
        client_id = self._google_client_id()
        if not client_id:
            raise ValueError("Google OAuth client id is not configured")

        query = urlencode(
            {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "access_type": "offline",
                "prompt": "consent",
            }
        )
        return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"

    def exchange_google_code(self, *, code: str, redirect_uri: str) -> str:
        """Exchange an OAuth authorization code for Google ID token."""
        client_id = self._google_client_id()
        client_secret = self._google_client_secret()
        if not client_id or not client_secret:
            raise ValueError("Google OAuth client credentials are not configured")

        response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
        if response.status_code >= 400:
            raise ValueError("Google OAuth token exchange failed")

        payload = response.json()
        id_token = payload.get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise ValueError("Google OAuth response missing id_token")
        return id_token

    def verify_google_id_token(self, *, id_token: str) -> dict[str, Any]:
        """Verify a Google ID token and return identity claims."""
        response = requests.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": id_token},
            timeout=15,
        )
        if response.status_code >= 400:
            raise ValueError("Invalid Google ID token")

        claims = response.json()
        aud = claims.get("aud")
        email = claims.get("email")
        sub = claims.get("sub")
        expected_aud = self._google_client_id()
        if expected_aud and aud != expected_aud:
            raise ValueError("Google ID token audience mismatch")
        if not isinstance(email, str) or not email:
            raise ValueError("Google ID token missing email")
        if not isinstance(sub, str) or not sub:
            raise ValueError("Google ID token missing subject")
        return dict(claims)

    def authenticate_google_id_token(self, *, id_token: str) -> User:
        """Authenticate a user via Google ID token and auto-provision if needed."""
        claims = self.verify_google_id_token(id_token=id_token)
        email = str(claims["email"]).strip().lower()
        existing = self.user_service.get_user_by_email(email)
        if existing is not None:
            return existing

        display_name = str(
            claims.get("name") or claims.get("given_name") or email.split("@", 1)[0]
        ).strip()
        google_subject = str(claims["sub"])
        avatar_url = claims.get("picture")
        user = self.user_service.create_user(
            user_id=f"google-{google_subject}",
            email=email,
            display_name=display_name or "Google User",
            google_subject_id=google_subject,
            avatar_url=(
                str(avatar_url).strip()
                if isinstance(avatar_url, str) and avatar_url.strip()
                else None
            ),
            auth_provider="google",
        )
        return user

    def authenticate_google_code(
        self,
        *,
        code: str,
        redirect_uri: str,
    ) -> User:
        """Authenticate Google OAuth code and return local user account."""
        id_token = self.exchange_google_code(code=code, redirect_uri=redirect_uri)
        return self.authenticate_google_id_token(id_token=id_token)

    def register_user(
        self,
        *,
        user_id: str,
        email: str,
        display_name: str,
        password: str,
    ) -> User:
        """Register a new user and persist password hash in service store."""
        user = self.user_service.create_user(
            user_id=user_id,
            email=email,
            display_name=display_name,
        )
        self._password_hashes[user.id] = self.password_hasher.hash_password(password)
        return user

    def authenticate(self, *, email: str, password: str) -> User | None:
        """Authenticate user by email and password.

        Returns:
            The authenticated user if credentials are valid and user is active.
            Otherwise returns None.
        """
        user = self.user_service.get_user_by_email(email)
        if user is None or not user.is_active:
            return None

        stored_hash = self._password_hashes.get(user.id)
        if stored_hash is None:
            return None

        if not self.password_hasher.verify_password(password, stored_hash):
            return None

        return user

    def get_user(self, user_id: str) -> User | None:
        """Fetch a user by identifier."""
        return self.user_service.get_user(user_id)

    def issue_token(self, user: User, expires_minutes: int = 60) -> str:
        """Issue a signed access token for an authenticated user."""
        return self.token_service.create_access_token(
            user_id=user.id,
            email=user.email,
            expires_minutes=expires_minutes,
        )

    def issue_token_pair(self, user: User, expires_minutes: int = 60) -> dict[str, str]:
        """Issue an access and refresh token pair for an authenticated user."""
        access_token = self.issue_token(user=user, expires_minutes=expires_minutes)
        refresh_token = self.token_service.create_refresh_token(
            user_id=user.id,
            email=user.email,
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    def refresh_access_token(
        self, refresh_token: str, expires_minutes: int = 60
    ) -> str:
        """Rotate a refresh token into a new access token."""
        claims = self.token_service.verify_refresh_token(refresh_token)
        user = self.get_user(str(claims["sub"]))
        if user is None or not user.is_active:
            raise ValueError("User not found or inactive")
        return self.issue_token(user=user, expires_minutes=expires_minutes)

    def logout(self, refresh_token: str | None = None) -> None:
        """Invalidate refresh token state for logout semantics."""
        if not refresh_token:
            return
        self.token_service.revoke_refresh_token(refresh_token)

    def validate_token(self, token: str) -> dict[str, Any]:
        """Validate a JWT access token and return claims."""
        return self.token_service.verify_access_token(token)

"""Authentication API routes."""

from __future__ import annotations

import json
import os
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from backend.api.dependencies import (
    AuthServiceDependency,
    OwnershipContextDependency,
    RequiredCurrentUserDependency,
    generate_user_id,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    """Request payload for user registration."""

    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)
    display_name: str = Field(..., min_length=1)


class RegisterResponse(BaseModel):
    """Response payload for user registration."""

    user_id: str
    email: str
    display_name: str


class LoginRequest(BaseModel):
    """Request payload for login."""

    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    """Response payload for login."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Request payload for refresh token exchange."""

    refresh_token: str = Field(..., min_length=1)


class LogoutRequest(BaseModel):
    """Request payload for logout."""

    refresh_token: str | None = None


class OAuthStartResponse(BaseModel):
    """Response payload for OAuth authorization start."""

    provider: str
    authorization_url: str
    state: str


class OAuthExchangeRequest(BaseModel):
    """Request payload for OAuth code exchange foundation."""

    code: str = Field(..., min_length=1)
    redirect_uri: str = Field(..., min_length=1)


class OAuthExchangeResponse(BaseModel):
    """Response payload for OAuth foundation state."""

    provider: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class CurrentUserResponse(BaseModel):
    """Response payload for current authenticated user."""

    user_id: str
    email: str
    display_name: str
    avatar_url: str | None = None
    project_id: str | None = None


def _default_google_callback_uri(request: Request) -> str:
    configured = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "").strip()
    if configured:
        return configured
    return str(request.url_for("oauth_google_callback"))


def _frontend_post_login_url() -> str:
    configured = os.getenv("FRONTEND_POST_LOGIN_URL", "").strip()
    if configured:
        return configured
    return "http://127.0.0.1:5173/chat"


@router.post("/register", response_model=RegisterResponse)
def register(
    payload: RegisterRequest,
    auth_service: AuthServiceDependency,
) -> RegisterResponse:
    """Register a new user."""
    try:
        user = auth_service.register_user(
            user_id=generate_user_id(),
            email=payload.email,
            display_name=payload.display_name,
            password=payload.password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return RegisterResponse(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
    )


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    auth_service: AuthServiceDependency,
) -> LoginResponse:
    """Authenticate a user and issue an access token."""
    user = auth_service.authenticate(email=payload.email, password=payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    tokens = auth_service.issue_token_pair(user)
    return LoginResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
    )


@router.post("/refresh", response_model=LoginResponse)
def refresh_token(
    payload: RefreshTokenRequest,
    auth_service: AuthServiceDependency,
) -> LoginResponse:
    """Exchange refresh token for a new access token."""
    try:
        access_token = auth_service.refresh_access_token(payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from exc

    return LoginResponse(
        access_token=access_token,
        refresh_token=payload.refresh_token,
    )


@router.post("/logout")
def logout(
    payload: LogoutRequest,
    auth_service: AuthServiceDependency,
) -> dict[str, str]:
    """Invalidate refresh token state for logout semantics."""
    auth_service.logout(payload.refresh_token)
    return {"status": "ok"}


@router.get("/me", response_model=CurrentUserResponse)
def me(
    current_user: RequiredCurrentUserDependency,
    auth_service: AuthServiceDependency,
    ownership_context: OwnershipContextDependency,
) -> CurrentUserResponse:
    """Return the current authenticated user."""
    user_id = current_user.user_id
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    user = auth_service.get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return CurrentUserResponse(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        project_id=ownership_context.get("project_id"),
    )


@router.get("/profile", response_model=CurrentUserResponse)
def profile(
    current_user: RequiredCurrentUserDependency,
    auth_service: AuthServiceDependency,
    ownership_context: OwnershipContextDependency,
) -> CurrentUserResponse:
    """Alias endpoint for current authenticated profile."""
    return me(
        current_user=current_user,
        auth_service=auth_service,
        ownership_context=ownership_context,
    )


@router.get("/oauth/google/start", response_model=OAuthStartResponse)
def oauth_google_start(
    request: Request,
    auth_service: AuthServiceDependency,
) -> OAuthStartResponse:
    """Return Google OAuth authorization URL for login flow."""
    state = generate_user_id()
    redirect_uri = _default_google_callback_uri(request)
    try:
        authorization_url = auth_service.build_google_authorization_url(
            redirect_uri=redirect_uri,
            state=state,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured.",
        ) from exc
    return OAuthStartResponse(
        provider="google",
        authorization_url=authorization_url,
        state=state,
    )


@router.post("/oauth/google/exchange", response_model=OAuthExchangeResponse)
def oauth_google_exchange(
    payload: OAuthExchangeRequest,
    auth_service: AuthServiceDependency,
) -> OAuthExchangeResponse:
    """Exchange Google OAuth code for local JWT session tokens."""
    try:
        user = auth_service.authenticate_google_code(
            code=payload.code,
            redirect_uri=payload.redirect_uri,
        )
        tokens = auth_service.issue_token_pair(user)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    return OAuthExchangeResponse(
        provider="google",
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
    )


@router.get("/oauth/google/callback", name="oauth_google_callback")
def oauth_google_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    request: Request = None,
    auth_service: AuthServiceDependency = None,
) -> HTMLResponse:
    """Handle Google OAuth callback and redirect to frontend with tokens."""
    if error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google OAuth error: {error}",
        )
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Google authorization code",
        )
    if request is None or auth_service is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth callback dependencies are unavailable",
        )

    redirect_uri = _default_google_callback_uri(request)
    user = auth_service.authenticate_google_code(code=code, redirect_uri=redirect_uri)
    tokens = auth_service.issue_token_pair(user)

    frontend_url = _frontend_post_login_url()
    query = urlencode(
        {
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": "bearer",
            "state": state or "",
        }
    )
    payload_json = json.dumps(
        {
            "source": "sand-swap-oauth",
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": "bearer",
            "state": state or "",
        }
    )
    frontend_with_query = f"{frontend_url}?{query}"
    html = f"""
<!doctype html>
<html>
<head>
    <meta charset=\"utf-8\" />
    <title>Signing in...</title>
</head>
<body>
    <script>
        (function () {{
            var payload = {payload_json};
            try {{
                if (window.opener && !window.opener.closed) {{
                    window.opener.postMessage(payload, "*");
                    window.close();
                    return;
                }}
            }} catch (err) {{}}
            window.location.replace({json.dumps(frontend_with_query)});
        }})();
    </script>
    <p>Completing sign in...</p>
</body>
</html>
"""
    return HTMLResponse(content=html)


@router.get("/session")
def session_context(
    current_user: RequiredCurrentUserDependency,
    auth_service: AuthServiceDependency,
    ownership_context: OwnershipContextDependency,
) -> dict[str, str]:
    """Return authenticated user and workspace session context."""
    user_id = current_user.user_id
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    user = auth_service.get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return {
        "user_id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "project_id": ownership_context.get("project_id", "default"),
    }

"""API router composition for SandSwap AI."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.dependencies import (
    AuthServiceDependency,
    RequiredCurrentUserDependency,
    generate_user_id,
)
from backend.api.health import router as health_router
from backend.chat.api.chat_routes import router as chat_router
from backend.memory.api.memory_routes import router as memory_router
from backend.rag.api.document_routes import router as document_router


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
    token_type: str = "bearer"


class MeResponse(BaseModel):
    """Response payload for current authenticated user."""

    user_id: str
    email: str
    display_name: str


router = APIRouter()


@router.post("/auth/register", response_model=RegisterResponse)
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


@router.post("/auth/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    auth_service: AuthServiceDependency,
) -> LoginResponse:
    """Authenticate user and issue bearer token."""
    user = auth_service.authenticate(email=payload.email, password=payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return LoginResponse(access_token=auth_service.issue_token(user))


@router.get("/auth/me", response_model=MeResponse)
def me(
    current_user: RequiredCurrentUserDependency,
    auth_service: AuthServiceDependency,
) -> MeResponse:
    """Return the current authenticated user."""
    if current_user.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    user = auth_service.get_user(current_user.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return MeResponse(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
    )


router.include_router(health_router)
router.include_router(chat_router)
router.include_router(memory_router)
router.include_router(document_router)

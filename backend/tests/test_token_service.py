"""Regression tests for JWT token secret handling."""

from __future__ import annotations

from backend.auth.token_service import TokenService


def test_short_secret_uses_stronger_signing_key() -> None:
    """Tokens created with short configured secrets use normalized strong keys."""
    service = TokenService(secret="test-secret")

    token = service.create_access_token(user_id="user-1", email="user@example.com")

    claims = service.verify_access_token(token)
    assert claims["sub"] == "user-1"
    assert len(service.secret.encode("utf-8")) >= 32


def test_legacy_short_secret_tokens_remain_verifiable() -> None:
    """Previously-issued short-secret tokens remain valid after key normalization."""
    jwt = TokenService._jwt_module()
    service = TokenService(secret="legacy-secret")

    legacy_payload = {
        "sub": "legacy-user",
        "email": "legacy@example.com",
        "token_type": "access",
        "iat": 1,
        "exp": 4_102_444_800,
    }
    legacy_token = jwt.encode(legacy_payload, "legacy-secret", algorithm="HS256")

    claims = service.verify_access_token(str(legacy_token))
    assert claims["sub"] == "legacy-user"


def test_default_secret_meets_hs256_length_requirements() -> None:
    """Default runtime secret should avoid weak-key warnings."""
    service = TokenService(secret=None)

    assert len(service.secret.encode("utf-8")) >= 32

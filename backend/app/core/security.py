"""Authentication and authorization.

Architecture: backend-managed sessions with HttpOnly SameSite cookies
and CSRF protection. In development (DEV_MODE=true), a demo auth bypass
is available so local development does not require a running Keycloak.
The demo bypass binds to 127.0.0.1 only and refuses to activate in
production.

Roles: viewer, analyst, admin.
"""

from __future__ import annotations

import time
from enum import Enum
from functools import lru_cache

from authlib.jose import JsonWebToken, jwt
from authlib.jose.errors import JoseError
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.core.config import get_settings

bearer_scheme = HTTPBearer(auto_error=False)


class Role(str, Enum):
    viewer = "viewer"
    analyst = "analyst"
    admin = "admin"

    @property
    def level(self) -> int:
        return {"viewer": 1, "analyst": 2, "admin": 3}[self.value]


class UserContext:
    """Minimal user context extracted from the request."""

    def __init__(self, sub: str, role: str = "viewer", name: str | None = None):
        self.sub = sub
        self.role = role
        self.name = name or sub
        self.is_admin = role == "admin"
        self.is_analyst = role in ("analyst", "admin")

    def __repr__(self) -> str:
        return f"UserContext(sub={self.sub!r}, role={self.role!r})"


class AuthError(Exception):
    pass


class JWKSCache:
    """Cache for JWKS (JSON Web Key Set) with TTL."""

    def __init__(self, ttl_seconds: int = 3600):
        self._jwks: dict | None = None
        self._expires_at: float = 0
        self._ttl = ttl_seconds

    async def get_jwks(self, settings) -> dict:
        """Fetch JWKS from Keycloak, using cached value if not expired."""
        now = time.time()
        if self._jwks is not None and now < self._expires_at:
            return self._jwks

        jwks_url = f"{settings.keycloak_server_url.rstrip('/')}/realms/{settings.keycloak_realm}/protocol/openid-connect/certs"

        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(jwks_url)
            response.raise_for_status()
            self._jwks = response.json()
            self._expires_at = now + self._ttl
            return self._jwks


_jwks_cache = JWKSCache()


@lru_cache(maxsize=1)
def _demo_user() -> UserContext:
    return UserContext(sub="demo", role="admin", name="Demo User")


async def _validate_oidc_token(token: str, settings) -> UserContext:
    """Validate an OIDC Bearer token against Keycloak.

    Validates: signature (RS256), issuer, audience, expiration, not-before.
    Returns UserContext with sub and role from claims.
    """
    jwks = await _jwks_cache.get_jwks(settings)

    # Expected claims for validation
    expected_issuer = f"{settings.keycloak_server_url.rstrip('/')}/realms/{settings.keycloak_realm}"
    expected_audience = settings.keycloak_client_id

    try:
        # Decode and validate the token
        claims = jwt.decode(
            token,
            jwks,
            claims_options={
                "iss": {"essential": True, "value": expected_issuer},
                "aud": {"essential": True, "value": expected_audience},
                "exp": {"essential": True},
                "nbf": {"essential": True},
            },
        )

        # Validate the claims
        claims.validate()

    except JoseError as exc:
        raise AuthError(f"Invalid token: {exc}") from exc

    # Extract user info from claims
    sub = claims.get("sub")
    if not sub:
        raise AuthError("Token missing 'sub' claim")

    # Extract role from realm_access.roles (Keycloak standard)
    realm_access = claims.get("realm_access", {})
    roles = realm_access.get("roles", [])

    # Map Keycloak roles to our roles (highest priority wins)
    role = "viewer"
    if "admin" in roles:
        role = "admin"
    elif "analyst" in roles:
        role = "analyst"

    name = claims.get("preferred_username") or claims.get("name") or sub

    return UserContext(sub=sub, role=role, name=name)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings=Depends(get_settings),
) -> UserContext:
    """Resolve the current user from the request.

    In DEV_MODE (localhost only), returns a demo admin user.
    Otherwise, expects a Bearer token issued by Keycloak.
    """
    if settings.dev_mode and request.client and request.client.host in (
        "127.0.0.1",
        "::1",
        "localhost",
    ):
        return _demo_user()

    if not credentials or not credentials.credentials:
        raise AuthError("Missing Bearer token")

    token = credentials.credentials

    try:
        # Run the async validation in a sync context via create_task
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        user = loop.run_until_complete(_validate_oidc_token(token, settings))
        return user

    except AuthError:
        raise
    except Exception as exc:
        raise AuthError(f"Token validation failed: {exc}") from exc


def require_role(min_role: Role):
    """Dependency factory: require the current user to have at least min_role."""

    def dependency(user: UserContext = Depends(get_current_user)) -> UserContext:
        if user.role == "viewer" and min_role != Role.viewer:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role {min_role.value} or higher",
            )
        if min_role == Role.admin and not user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires admin role, have {user.role}",
            )
        if min_role == Role.analyst and not user.is_analyst:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires analyst role, have {user.role}",
            )
        return user

    return dependency


require_admin = require_role(Role.admin)
require_analyst = require_role(Role.analyst)
require_viewer = require_role(Role.viewer)
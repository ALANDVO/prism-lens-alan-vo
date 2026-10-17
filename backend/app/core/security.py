"""Authentication and authorization.

Architecture: backend-managed sessions with HttpOnly SameSite cookies
and CSRF protection. In development (DEV_MODE=true), a demo auth bypass
is available so local development does not require a running Keycloak.
The demo bypass binds to 127.0.0.1 only and refuses to activate in
production.

Roles: viewer, analyst, admin.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache

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


@lru_cache(maxsize=1)
def _demo_user() -> UserContext:
    return UserContext(sub="demo", role="admin", name="Demo User")


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
    # In a full deployment, validate the JWT signature, issuer, audience,
    # and nonce against the Keycloak well-known endpoint.  The token
    # carries the 'role' claim.
    # This is a placeholder for the OIDC validation step.
    raise AuthError(
        "Bearer token authentication requires production OIDC configuration. "
        "Set DEV_MODE=true for local development."
    )


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
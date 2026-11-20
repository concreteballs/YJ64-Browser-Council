from dataclasses import dataclass
from functools import lru_cache
from uuid import NAMESPACE_URL, UUID, uuid5

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from starlette.concurrency import run_in_threadpool


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthSettings:
    issuer: str
    audience: str
    jwks_url: str


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    issuer: str
    subject: str


def get_auth_settings() -> AuthSettings | None:
    import os

    issuer = os.getenv("OIDC_ISSUER", "").strip()
    audience = os.getenv("OIDC_AUDIENCE", "").strip()
    jwks_url = os.getenv("OIDC_JWKS_URL", "").strip()
    if not issuer or not audience or not jwks_url:
        return None
    return AuthSettings(issuer=issuer, audience=audience, jwks_url=jwks_url)


@lru_cache(maxsize=8)
def get_jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_jwk_set=True, lifespan=300, timeout=5)


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Principal:
    settings = get_auth_settings()
    if settings is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        client = get_jwks_client(settings.jwks_url)
        signing_key = await run_in_threadpool(
            client.get_signing_key_from_jwt,
            credentials.credentials,
        )
        claims = jwt.decode(
            credentials.credentials,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.audience,
            issuer=settings.issuer,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise jwt.InvalidTokenError("Missing subject")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # Stable, issuer-scoped internal UUID; raw OIDC subject is never exposed as a DB key.
    principal_id = uuid5(NAMESPACE_URL, f"browser-council:{settings.issuer}:{subject}")
    return Principal(user_id=principal_id, issuer=settings.issuer, subject=subject)

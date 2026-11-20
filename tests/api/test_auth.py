import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import NAMESPACE_URL, uuid5

import jwt
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from apps.api.auth import AuthSettings, get_current_principal


class AuthenticationTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_oidc_configuration_fails_closed(self):
        with patch("apps.api.auth.get_auth_settings", return_value=None):
            with self.assertRaises(HTTPException) as raised:
                await get_current_principal(None)
        self.assertEqual(raised.exception.status_code, 503)

    async def test_missing_bearer_token_is_rejected(self):
        settings = AuthSettings("https://issuer.example", "browser-council", "https://issuer.example/keys")
        with patch("apps.api.auth.get_auth_settings", return_value=settings):
            with self.assertRaises(HTTPException) as raised:
                await get_current_principal(None)
        self.assertEqual(raised.exception.status_code, 401)

    async def test_verified_oidc_subject_maps_to_stable_internal_uuid(self):
        settings = AuthSettings("https://issuer.example", "browser-council", "https://issuer.example/keys")
        claims = {"iss": settings.issuer, "aud": settings.audience, "sub": "opaque-user-123"}
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="signed.jwt")
        client = SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key="public-key"))

        with (
            patch("apps.api.auth.get_auth_settings", return_value=settings),
            patch("apps.api.auth.get_jwks_client", return_value=client),
            patch("apps.api.auth.run_in_threadpool", new=AsyncMock(return_value=SimpleNamespace(key="public-key"))),
            patch("apps.api.auth.jwt.decode", return_value=claims) as decode,
        ):
            principal = await get_current_principal(credentials)

        decode.assert_called_once()
        self.assertEqual(decode.call_args.kwargs["algorithms"], ["RS256"])
        self.assertEqual(principal.user_id, uuid5(NAMESPACE_URL, f"browser-council:{settings.issuer}:opaque-user-123"))
        self.assertEqual(principal.subject, "opaque-user-123")

    async def test_invalid_token_is_rejected(self):
        settings = AuthSettings("https://issuer.example", "browser-council", "https://issuer.example/keys")
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad.jwt")
        client = SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key="public-key"))

        with (
            patch("apps.api.auth.get_auth_settings", return_value=settings),
            patch("apps.api.auth.get_jwks_client", return_value=client),
            patch("apps.api.auth.run_in_threadpool", new=AsyncMock(return_value=SimpleNamespace(key="public-key"))),
            patch("apps.api.auth.jwt.decode", side_effect=jwt.InvalidTokenError("bad signature")),
        ):
            with self.assertRaises(HTTPException) as raised:
                await get_current_principal(credentials)
        self.assertEqual(raised.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()

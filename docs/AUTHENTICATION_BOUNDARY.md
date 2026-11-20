# Authentication boundary

Browser Council uses a provider-neutral OpenID Connect (OIDC) access-token
verifier. Configure `OIDC_ISSUER`, `OIDC_AUDIENCE` and `OIDC_JWKS_URL`
from the selected identity provider. Tokens are verified against cached JWKS
keys, with the allowed signing algorithm pinned to RS256 and issuer/audience,
expiry and subject required. Missing configuration fails closed (503); absent
or invalid bearer tokens are rejected (401).

The verified issuer and opaque subject are mapped to a deterministic internal
UUIDv5 principal. The issuer is part of the namespace input, so equal subject
strings from different issuers do not collide. This is an internal identity
mapping, not automatic account linking. Linking multiple identity providers
must require an explicit verified account-link flow.

Protected routes must depend on `get_current_principal` and pass
`principal.user_id` into `Database.tenant_transaction`. Never derive the
principal from request JSON, query parameters, or an unverified header. Do
not log access tokens or return raw subject values in ordinary API responses.

No identity provider has been selected or provisioned yet. Until its issuer,
audience and JWKS endpoint are configured, protected endpoints must remain
unavailable. This implementation does not provide registration, password
storage, refresh-token handling, account recovery or social login UI.

"""Fail-closed OAuth2 access-token verifier. Not yet wired into API routes.

The caller MUST supply the verified API audience and issuer, and MUST enforce
per-resource authorization afterwards. Browser ID tokens are not API grants.
"""
from dataclasses import dataclass
from urllib.parse import urlparse

import jwt


class AuthenticationRejected(ValueError):
    """A request is not authenticated; do not expose token or JWK details."""


class IdentityNotConfigured(RuntimeError):
    """An operator must configure the identity provider before enabling auth."""


@dataclass(frozen=True)
class Principal:
    issuer: str
    subject: str

    @property
    def stable_id(self) -> tuple[str, str]:
        # OIDC subject is only unique inside the issuer's namespace.
        return (self.issuer, self.subject)


def validate_oidc_configuration(issuer: str, audience: str, jwks_url: str) -> None:
    if not issuer or not audience or not jwks_url:
        raise IdentityNotConfigured("OIDC resource-server configuration is incomplete")
    for uri in (issuer, jwks_url):
        parsed = urlparse(uri)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
                parsed.password or parsed.fragment or parsed.port not in (None, 443)):
            raise IdentityNotConfigured("OIDC issuer and keys must be trusted HTTPS URLs")


def verify_access_token(authorization: str | None, *, issuer: str,
                        audience: str, signing_key_resolver) -> Principal:
    """Validate an OAuth access token for this API, not a browser-provided user_id.

    signing_key_resolver is a trusted, bounded JWKS lookup selected by the
    operator, never a URL or JWK taken from unverified JWT headers.
    """
    if not issuer or not audience or not callable(signing_key_resolver):
        raise IdentityNotConfigured("OIDC validation is not configured")
    if not authorization or not isinstance(authorization, str):
        raise AuthenticationRejected("Valid authentication is required")
    parts = authorization.split(" ")
    if (len(parts) != 2 or parts[0].lower() != "bearer" or
            len(parts[1]) > 8192 or not parts[1]):
        raise AuthenticationRejected("Valid authentication is required")
    token = parts[1]
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str) or not header["kid"]:
            raise AuthenticationRejected("Valid authentication is required")
        signing_key = signing_key_resolver(token)
        claims = jwt.decode(
            token, signing_key, algorithms=["RS256"], issuer=issuer, audience=audience,
            options={"require": ["sub", "iss", "aud", "exp", "iat"]},
            leeway=30,
        )
        sub = claims.get("sub")
        if not isinstance(sub, str) or not sub.strip() or len(sub) > 256:
            raise AuthenticationRejected("Valid authentication is required")
        return Principal(issuer=issuer, subject=sub)
    except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
        raise AuthenticationRejected("Valid authentication is required") from None


def build_jwks_resolver(jwks_url: str, *, issuer: str, audience: str):
    """Build a cached trusted JWKS resolver. May perform bounded HTTPS I/O."""
    validate_oidc_configuration(issuer, audience, jwks_url)
    client = jwt.PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=300,
                           cache_keys=False, timeout=3)
    return lambda token: client.get_signing_key_from_jwt(token).key

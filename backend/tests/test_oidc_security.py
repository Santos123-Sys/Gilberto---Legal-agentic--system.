"""Verifier unit tests. Signed tokens, no network or identity provider dependency."""
import time
import unittest

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from security.oidc import (AuthenticationRejected, IdentityNotConfigured,
                            build_jwks_resolver, validate_oidc_configuration,
                            verify_access_token)


class AccessTokenVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public_key = cls.key.public_key()

    def token(self, **overrides):
        payload = {
            "iss": "https://id.example.test/",
            "sub": "user-123",
            "aud": "gilberto-api",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()) - 1,
        }
        payload.update(overrides)
        return jwt.encode(payload, self.key, algorithm="RS256", headers={"kid": "test-key"})

    def check(self, token):
        return verify_access_token("Bearer " + token, issuer="https://id.example.test/",
                                   audience="gilberto-api", signing_key_resolver=lambda _: self.public_key)

    def test_valid_principal_is_issuer_and_subject_not_client_user_id(self):
        principal = self.check(self.token())
        self.assertEqual(principal.stable_id, ("https://id.example.test/", "user-123"))
        self.assertNotEqual(principal.stable_id, ("other-issuer", "user-123"))

    def test_missing_and_malformed_authorization_rejected(self):
        for value in (None, "", "Basic xyz", "Bearer", "Bearer a b", "bearer ", "Bearer " + "a"*8193):
            with self.subTest(header=str(value)[:20]), self.assertRaises(AuthenticationRejected):
                verify_access_token(value, issuer="https://id.example.test/",
                                    audience="gilberto-api", signing_key_resolver=lambda _: self.public_key)

    def test_bad_issuer_audience_expiration_and_missing_subject_are_rejected(self):
        for bad in ({"iss": "https://wrong.example.test/"}, {"aud": "other-api"},
                    {"exp": int(time.time()) - 10000}, {"sub": ""}):
            with self.subTest(claim=bad), self.assertRaises(AuthenticationRejected):
                self.check(self.token(**bad))

    def test_unsigned_and_hmac_algorithm_confusion_are_rejected(self):
        unsigned = jwt.encode({"sub": "u"}, key="", algorithm="none", headers={"kid": "test-key"})
        hmac = jwt.encode({"sub": "u"}, "private", algorithm="HS256", headers={"kid": "test-key"})
        for token in (unsigned, hmac):
            with self.assertRaises(AuthenticationRejected):
                self.check(token)

    def test_forged_signing_key_rejected(self):
        attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        forged = jwt.encode({"iss": "https://id.example.test/", "aud": "gilberto-api",
                             "sub": "u", "exp": int(time.time()) + 3600, "iat": int(time.time())},
                            attacker_key, algorithm="RS256", headers={"kid": "test-key"})
        with self.assertRaises(AuthenticationRejected):
            self.check(forged)

    def test_operator_must_configure_trusted_urls(self):
        validate_oidc_configuration("https://id.example.test/", "gilberto-api", "https://id.example.test/keys")
        for issuer, audience, keys in (
            ("", "gilberto-api", "https://id.example.test/jwks"),
            ("http://id.example.test", "gilberto-api", "https://id.example.test/jwks"),
            ("https://id.example.test", "", "https://id.example.test/jwks"),
            ("https://id.example.test", "gilberto-api", "http://id.example.test/jwks"),
            ("https://id.example.test", "gilberto-api", "https://user:secret@id.example.test/jwks"),
        ):
            with self.assertRaises(IdentityNotConfigured):
                validate_oidc_configuration(issuer, audience, keys)

    def test_missing_configuration_fails_closed(self):
        with self.assertRaises(IdentityNotConfigured):
            verify_access_token("Bearer " + self.token(), issuer="", audience="gilberto-api",
                                signing_key_resolver=lambda _: self.public_key)

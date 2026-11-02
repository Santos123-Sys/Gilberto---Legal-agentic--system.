"""Object ownership policy is deny-by-default, even for legacy checkpoints."""
import unittest

from security.authorization import AccessDenied, require_session_owner
from security.oidc import Principal


class OwnershipPolicyTests(unittest.TestCase):
    def test_authenticated_owner_can_access_only_exact_issuer_subject_pair(self):
        owner = Principal("https://identity.example/", "owner-A")
        resource = {"id": "opaque-session-uuid", "owner_issuer": "https://identity.example/",
                    "owner_subject": "owner-A"}
        require_session_owner(owner, resource)
        for other in (
            Principal("https://identity.example/", "owner-B"),
            Principal("https://untrusted-identity.example/", "owner-A"),
        ):
            with self.assertRaises(AccessDenied):
                require_session_owner(other, resource)

    def test_legacy_or_unowned_sessions_never_allow_first_to_claim(self):
        principal = Principal("https://identity.example/", "owner-A")
        for resource in (
            {}, {"id": "legacy-uuid"}, {"owner_issuer": principal.issuer},
            {"owner_subject": principal.subject}, {"owner_issuer": None, "owner_subject": None},
        ):
            with self.assertRaises(AccessDenied):
                require_session_owner(principal, resource)

    def test_client_user_id_field_does_not_grant_access(self):
        principal = Principal("https://identity.example/", "owner-A")
        with self.assertRaises(AccessDenied):
            require_session_owner(principal, {"config": {"user_id": "owner-A"},
                                                "owner_issuer": principal.issuer,
                                                "owner_subject": "owner-B"})

    def test_unverified_type_never_grants_access(self):
        with self.assertRaises(AccessDenied):
            require_session_owner({"issuer": "https://identity.example/", "subject": "owner-A"},
                                  {"owner_issuer": "https://identity.example/", "owner_subject": "owner-A"})

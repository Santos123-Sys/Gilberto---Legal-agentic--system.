"""Official-source *location* checks for Brazilian legal authorities.

IMPORTANT: an official-looking URL and an official hostname do NOT certify
existence, applicable text, case holding, publication, temporal validity or
precedential strength. These require separately retrieved signed/official
content, version checks and expert adjudication.
"""
from urllib.parse import urlsplit

OFFICIAL_HOSTS = {
    "planalto.gov.br": "federal_legislation",
    "www.planalto.gov.br": "federal_legislation",
    "stf.jus.br": "federal_court",
    "www.stf.jus.br": "federal_court",
    "portal.stf.jus.br": "federal_court",
    "stj.jus.br": "federal_court",
    "www.stj.jus.br": "federal_court",
    "scon.stj.jus.br": "federal_court",
    "tst.jus.br": "labor_court",
    "www.tst.jus.br": "labor_court",
    "cvm.gov.br": "capital_markets_regulator",
    "www.gov.br": "government_portal",
    "conteudo.cvm.gov.br": "capital_markets_regulator",
    "cade.gov.br": "competition_regulator",
    "www.cade.gov.br": "competition_regulator",
    "cnj.jus.br": "judiciary_metadata",
    "www.cnj.jus.br": "judiciary_metadata",
    "atos.cnj.jus.br": "judiciary_metadata",
}
# Explicitly restricted official subpaths for shared government portal.
GOV_BR_PREFIXES = ("/cvm/", "/cade/", "/anpd/", "/mj/", "/pt-br/servicos/")


def classify_official_location(url):
    """Static origin metadata, NOT remote link checking or current-law verification."""
    if not isinstance(url, str) or len(url) > 2048:
        return {"status": "untrusted_location", "authority_verified": False}
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower().rstrip(".")
        if (parts.scheme != "https" or not host or parts.username or parts.password
                or parts.port not in (None, 443) or parts.fragment):
            raise ValueError()
    except (ValueError, TypeError):
        return {"status": "untrusted_location", "authority_verified": False}
    if host not in OFFICIAL_HOSTS:
        return {"status": "untrusted_location", "authority_verified": False}
    if host == "www.gov.br" and not any(parts.path.startswith(p) for p in GOV_BR_PREFIXES):
        return {"status": "untrusted_location", "authority_verified": False}
    return {
        "status": "official_source_location_not_retrieved",
        "authority_verified": False,
        "source_type": OFFICIAL_HOSTS[host],
        "origin": parts.scheme + "://" + host,
        "limitations": "No retrieval, date, citation, authority or case-holding validation",
    }


def authority_claim_record(citation, source_url=None, *, as_of_date=None):
    """Create a transparent unverified authority claim requiring independent checking."""
    claim = str(citation or "").strip()[:500]
    source = classify_official_location(source_url)
    return {
        "citation": claim,
        "as_of_date": as_of_date,
        "source_location": source,
        "claim_status": "unverified_authority_claim",
        "must_retrieve_official_document": True,
        "must_review_temporal_validity": True,
        "must_review_legal_applicability": True,
    }

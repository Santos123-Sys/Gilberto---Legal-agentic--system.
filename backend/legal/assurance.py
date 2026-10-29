"""Deterministic conservative evidence report; never certifies Brazilian law."""
from legal.evidence import verify_contract_quote, document_digest
from legal.authority import authority_claim_record

MAX_CLAIMS = 200

def assess_claims(document_text, findings):
    results=[]
    for item in (findings or [])[:MAX_CLAIMS]:
        if not isinstance(item,dict):
            continue
        kind=item.get("evidence_kind","other")
        record={"agent":str(item.get("agent",""))[:120],
                "item":str(item.get("item",""))[:500],
                "kind":kind,
                "round":item.get("round")}
        excerpt=item.get("evidence")
        basis=item.get("legal_basis")
        if kind=="contract_quote":
            record["contract_source"]=verify_contract_quote(document_text,excerpt)
        else:
            record["contract_source"]={"status":"not_verified_as_contract_quote"}
        if basis:
            record["legal_authority"]=authority_claim_record(basis)
        results.append(record)
    verified=sum(row["contract_source"]["status"]=="present_in_supplied_document" for row in results)
    missing=sum(row["contract_source"]["status"]=="not_found" for row in results)
    legal_unverified=sum("legal_authority" in row for row in results)
    return {
        "jurisdiction":"BR",
        "status":"requires_qualified_brazilian_legal_review",
        "legal_conclusions_verified":False,
        "document_sha256":document_digest(document_text),
        "claims_examined":len(results),
        "document_passages_located":verified,
        "document_passages_not_found":missing,
        "authority_claims_unverified":legal_unverified,
        "unreviewed_claims":max(0,len(findings or [])-len(results)),
        "source_checks":results,
        "limitations":"Document text matching does not establish legal correctness, current law or expert validation",
    }

"""Validation of synthetic BR benchmark schema, NOT substantive legal scoring."""
from pathlib import Path
import json
import sys

EXPECTED_CATEGORIES = {
    "contract_clause","ambiguous_contract","fabricated_case","temporal_amendment",
    "overlapping_sources","ocr_uncertainty","prompt_injection","foreign_law",
    "financial_exposure","precedent_conflict",
}

def validate_corpus(path=None):
    if path is None:
        path=Path(__file__).with_name("cases.json")
    corpus=json.loads(Path(path).read_text(encoding="utf-8"))
    if corpus.get("schema_version")!=1 or corpus.get("scope")!="BRAZILIAN_LAW_ONLY":
        raise ValueError("Invalid BR benchmark corpus or incompatible version")
    cases=corpus.get("cases")
    if not isinstance(cases,list) or len(cases)<10:
        raise ValueError("At least 10 synthetic control cases are required")
    seen=set()
    categories=set()
    for case in cases:
        if not isinstance(case,dict) or not isinstance(case.get("scenario"),str) or not case["scenario"]:
            raise ValueError("A benchmark scenario is missing")
        case_id=case.get("id")
        if not isinstance(case_id,str) or not case_id.startswith("BR-SYN-") or case_id in seen:
            raise ValueError("Synthetic case identifier is duplicated or malformed")
        seen.add(case_id)
        categories.add(case.get("category"))
        if (case.get("jurisdiction")!="BR" or case.get("synthetic") is not True
                or case.get("lawyer_review_status")!="pending"
                or case.get("source_verification_status")!="NOT_VERIFIED"
                or case.get("gold_legal_answer") is not None
                or not case.get("expected_control")
                or not case.get("as_of_date")):
            raise ValueError("Unreviewed synthetic case may not be certified as legal truth")
    if categories!=EXPECTED_CATEGORIES:
        raise ValueError("All required audit/control categories must be present")
    return {
        "synthetic_cases":len(cases),
        "distinct_control_categories":len(categories),
        "expert_verified_legal_accuracy":None,
        "expert_scored_reasoning":None,
        "baseline_vs_new_legal_accuracy_ratio":None,
        "note":"Only control corpus schema validated; no legal truth benchmark executed",
    }

if __name__=="__main__":
    print(json.dumps(validate_corpus(),sort_keys=True))

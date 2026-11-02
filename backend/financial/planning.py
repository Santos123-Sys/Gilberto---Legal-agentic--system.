"""Brazilian legal review preflight: transparent planned calls and pricing bounds.

Do not pretend a full-price quote without the uploaded contract's input tokens.
"""
def estimate_plan(planned_calls, max_output_tokens, *, output_usd_per_million=0,
                  input_usd_per_million=0, hard_cap_usd=0):
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or v<0
           for v in (planned_calls,max_output_tokens,output_usd_per_million,
                     input_usd_per_million,hard_cap_usd)):
        raise ValueError("Expected nonnegative numeric configuration")
    if int(planned_calls)!=planned_calls or int(max_output_tokens)!=max_output_tokens:
        raise ValueError("Planned calls and output-token caps must be integers")
    max_output_total=int(planned_calls)*int(max_output_tokens)
    priced=bool(input_usd_per_million>0 and output_usd_per_million>0)
    return {
        "planned_model_calls":int(planned_calls),
        "maximum_possible_output_tokens":max_output_total,
        "priced_inputs_known":priced,
        "maximum_output_component_usd":round(max_output_total*output_usd_per_million/1_000_000,6)
             if priced else None,
        "per_review_estimated_cost_cap_usd":hard_cap_usd if hard_cap_usd>0 else None,
        "input_document_tokens_known":False,
        "complete_cost_quote_available":False,
        "cost_note":"Estimate excludes unknown input document/retrieval; not an invoice.",
    }

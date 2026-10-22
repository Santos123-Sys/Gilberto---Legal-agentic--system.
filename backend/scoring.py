"""Deterministic risk aggregation; model confidence is a weight, not accuracy."""
import math


def weighted_median(pairs):
    if not pairs:
        raise ValueError("Risk aggregation requires at least one specialist score")
    ordered = sorted(pairs)
    if any(not math.isfinite(score) or not math.isfinite(weight) or
           not 0 <= score <= 10 or not 0 < weight <= 5 for score, weight in ordered):
        raise ValueError("Invalid risk score or confidence weight")
    midpoint = sum(weight for _, weight in ordered) / 2
    cumulative = 0
    for index, (score, weight) in enumerate(ordered):
        cumulative += weight
        if math.isclose(cumulative, midpoint):
            return (score + ordered[index + 1][0]) / 2
        if cumulative > midpoint:
            return score


def classification_for(score):
    return "Crítico" if score >= 8 else "Relevante" if score >= 5 else "Aceitável"


def aggregate_clusters(summaries):
    pairs = [(s["parsed"]["aggregated_score"], s["parsed"]["confidence_aggregate"])
             for s in summaries.values()]
    score = weighted_median(pairs)
    return {"final_score": score, "final_classification": classification_for(score),
            "confidence": round(sum(weight for _, weight in pairs) / len(pairs), 1),
            "score_method": "confidence_weighted_median_v1",
            "confidence_note": "Model self-rating; not a calibrated probability of correctness."}

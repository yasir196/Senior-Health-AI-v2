from __future__ import annotations

from typing import Any

LOWER_IS_OFTEN_SIMPLER = {"clutter_score", "ocr_word_count", "ocr_line_count", "edge_density"}
HIGHER_IS_OFTEN_STRONGER = {"contrast_std", "face_area_ratio", "tiny_readability_edge_retention"}


def explain_group_difference(
    higher: dict[str, Any],
    lower: dict[str, Any],
    min_relative_gap: float = 0.08,
) -> list[dict[str, Any]]:
    """Describe observed feature differences, never causal claims."""
    hi = higher.get("feature_medians", {})
    lo = lower.get("feature_medians", {})
    findings = []
    for feature in sorted(set(hi) & set(lo)):
        a, b = hi[feature], lo[feature]
        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            continue
        scale = max(abs(a), abs(b), 1e-9)
        relative_gap = abs(a - b) / scale
        if relative_gap < min_relative_gap:
            continue
        direction = "higher" if a > b else "lower"
        interpretation = "observed_difference"
        if feature in LOWER_IS_OFTEN_SIMPLER:
            interpretation = "simpler_in_higher_ctr_group" if a < b else "more_complex_in_higher_ctr_group"
        elif feature in HIGHER_IS_OFTEN_STRONGER:
            interpretation = "stronger_in_higher_ctr_group" if a > b else "weaker_in_higher_ctr_group"
        findings.append({
            "feature": feature,
            "higher_ctr_median": a,
            "lower_ctr_median": b,
            "direction_in_higher_ctr_group": direction,
            "relative_gap": round(relative_gap, 4),
            "interpretation": interpretation,
            "claim_strength": "association_only",
        })
    return sorted(findings, key=lambda x: x["relative_gap"], reverse=True)


def build_why_report(patterns: dict[str, Any]) -> dict[str, Any]:
    categories = {}
    for name, category in patterns.get("category_patterns", {}).items():
        high = category["higher_ctr_group"]
        low = category["lower_ctr_group"]
        categories[name] = {
            "median_ctr": category["median_ctr"],
            "higher_ctr_observations": high["observations"],
            "lower_ctr_observations": low["observations"],
            "why_higher_ctr_group_looks_different": explain_group_difference(high, low),
            "why_lower_ctr_group_looks_different": explain_group_difference(low, high),
        }
    return {
        "method": "Explain observed winner/loser feature differences within topic category.",
        "important": "These are evidence-backed associations in this channel history, not proof that a feature caused CTR.",
        "categories": categories,
    }

from __future__ import annotations

import math
from collections import defaultdict
from statistics import median
from typing import Any

NUMERIC_FEATURES = (
    "brightness_mean", "contrast_std", "edge_density", "dark_pixel_ratio",
    "face_count", "face_area_ratio", "saliency_concentration", "clutter_score",
    "tiny_readability_edge_retention", "ocr_word_count", "ocr_line_count",
)

CATEGORY_KEYWORDS = {
    "exercise_mobility": ("exercise","chair","walk","walking","leg","balance","floor","movement","mobility"),
    "food_nutrition": ("food","eat","tea","calcium","peanut","protein","breakfast","nutrition"),
    "medicines": ("medicine","medicines","medication","drug","pill"),
    "symptoms": ("swollen","swelling","pain","stool","constipation","symptom"),
}


def _number(value: Any) -> float | None:
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def classify_category(title: str | None) -> str:
    text = (title or "").lower()
    scores = {category: sum(k in text for k in keys) for category, keys in CATEGORY_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else "educational_explainer"


def reliability_weight(impressions: Any, floor: int = 1000, full: int = 10000) -> float:
    n = _number(impressions) or 0
    if n < floor:
        return 0.0
    return round(min(1.0, math.log(n / floor + 1) / math.log(full / floor + 1)), 6)


def _flatten(row: dict[str, Any]) -> dict[str, Any]:
    features = dict(row.get("features") or {})
    ocr = dict(row.get("ocr") or {})
    performance = dict(row.get("performance") or {})
    return {
        **features,
        "ocr_word_count": ocr.get("word_count"),
        "ocr_line_count": ocr.get("line_count"),
        "ctr": performance.get("ctr"),
        "impressions": performance.get("impressions"),
        "title": performance.get("title"),
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"observations": len(rows)}
    ctrs = [_number(r.get("ctr")) for r in rows]
    ctrs = [v for v in ctrs if v is not None]
    result["median_ctr"] = round(median(ctrs), 4) if ctrs else None
    feature_medians = {}
    for name in NUMERIC_FEATURES:
        vals = [_number(r.get(name)) for r in rows]
        vals = [v for v in vals if v is not None]
        if vals:
            feature_medians[name] = round(median(vals), 6)
    result["feature_medians"] = feature_medians
    return result


def build_patterns(joined_rows: list[dict[str, Any]], min_impressions: int = 1000) -> dict[str, Any]:
    eligible = []
    excluded_low_impressions = 0
    for original in joined_rows:
        row = _flatten(original)
        ctr = _number(row.get("ctr"))
        impressions = _number(row.get("impressions"))
        if ctr is None or impressions is None or impressions < min_impressions:
            excluded_low_impressions += 1
            continue
        row["ctr"] = ctr
        row["impressions"] = impressions
        row["reliability_weight"] = reliability_weight(impressions, min_impressions)
        row["category"] = classify_category(row.get("title"))
        eligible.append(row)

    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        by_category[row["category"]].append(row)

    categories = {}
    winners = []
    losers = []
    for category, rows in sorted(by_category.items()):
        threshold = median([r["ctr"] for r in rows])
        high = [r for r in rows if r["ctr"] >= threshold]
        low = [r for r in rows if r["ctr"] < threshold]
        categories[category] = {
            "threshold_method": "within_category_median_ctr",
            "median_ctr": round(threshold, 4),
            "all": _summary(rows),
            "higher_ctr_group": _summary(high),
            "lower_ctr_group": _summary(low),
        }
        winners.extend(high)
        losers.extend(low)

    return {
        "schema_version": "0.1.0",
        "method": {
            "min_impressions": min_impressions,
            "comparison": "within-category median split",
            "causality_warning": "Associations only. Do not interpret feature differences as causal CTR effects.",
            "snapshot_warning": "Historical thumbnail snapshots require effective-date/performance-window mapping before variant-level attribution."
        },
        "eligible_observations": len(eligible),
        "excluded_observations": excluded_low_impressions,
        "winner_patterns": _summary(winners),
        "loser_patterns": _summary(losers),
        "category_patterns": categories,
    }

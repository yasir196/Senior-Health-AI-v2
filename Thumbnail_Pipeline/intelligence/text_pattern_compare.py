from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any

from .patterns import classify_category
from .text_psychology import pattern_sequence, psychology_tags


def compare_text_patterns(rows: list[dict[str, Any]], min_impressions: int = 1000) -> dict[str, Any]:
    """Compare psychological text patterns inside category; no generic score."""
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        perf, ocr = row.get("performance") or {}, row.get("ocr") or {}
        try:
            ctr = float(perf.get("ctr"))
            impressions = float(perf.get("impressions"))
        except (TypeError, ValueError):
            continue
        if impressions < min_impressions:
            continue
        category = classify_category(perf.get("title"))
        seq = pattern_sequence(ocr.get("text"))
        grouped[category][seq].append({
            "ctr": ctr, "impressions": impressions,
            "title": perf.get("title"), "thumbnail_text": ocr.get("text"),
            "psychology_tags": psychology_tags(ocr.get("text")),
        })

    output = {}
    for category, patterns in sorted(grouped.items()):
        records = []
        for seq, observations in patterns.items():
            ctrs = [x["ctr"] for x in observations]
            records.append({
                "pattern": seq,
                "observations": len(observations),
                "median_ctr": round(median(ctrs), 4),
                "total_impressions": int(sum(x["impressions"] for x in observations)),
                "examples": observations,
            })
        output[category] = sorted(records, key=lambda x: (x["median_ctr"], x["total_impressions"]), reverse=True)
    return {
        "method": "Within-category observed thumbnail-text psychology patterns; ordered by descriptive median CTR, not a causal score.",
        "categories": output,
    }

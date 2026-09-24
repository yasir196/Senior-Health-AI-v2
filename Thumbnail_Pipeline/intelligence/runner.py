from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from Thumbnail_Pipeline.io_policy import safe_output
from Thumbnail_Pipeline.intelligence.patterns import build_patterns
from Thumbnail_Pipeline.intelligence.explain import build_why_report
from Thumbnail_Pipeline.intelligence.text_pattern_compare import compare_text_patterns
from Thumbnail_Pipeline.intelligence.text_psychology import summarize_psychology
from Thumbnail_Pipeline.intelligence.recommendations import build_next_idea_rules, build_loser_suggestions
from Thumbnail_Pipeline.intelligence.settings import load_settings


def _eligible(rows: list[dict[str, Any]], min_impressions: int | None, settings: dict[str,Any] | None = None) -> list[dict[str, Any]]:
    cfg=settings or load_settings()
    allowed=set((cfg.get("eligibility") or {}).get("allowed_attribution_statuses") or [])
    out = []
    for row in rows:
        perf = row.get("performance") or {}
        try:
            status=str(perf.get("attribution_status") or (row.get("attribution") or {}).get("status") or "")
            if float(perf.get("impressions")) > 0 and (min_impressions is None or float(perf.get("impressions")) >= min_impressions) and perf.get("ctr") is not None and (not allowed or status in allowed):
                out.append(row)
        except (TypeError, ValueError):
            pass
    return out


def _split_by_category_median(rows: list[dict[str, Any]], patterns: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from Thumbnail_Pipeline.intelligence.patterns import classify_category
    winners, losers = [], []
    thresholds = {k: v["median_ctr"] for k, v in patterns["category_patterns"].items() if v.get("status")=="comparable" and v.get("median_ctr") is not None}
    for row in rows:
        perf = row.get("performance") or {}
        category = classify_category(row)
        try:
            ctr = float(perf.get("ctr"))
        except (TypeError, ValueError):
            continue
        if category not in thresholds:
            continue
        (winners if ctr >= thresholds[category] else losers).append(row)
    return winners, losers


def run_intelligence(joined_rows: list[dict[str, Any]], min_impressions: int | None = None, output_dir: str = "intelligence") -> dict[str, Any]:
    settings = load_settings()
    configured_floor = int(settings["eligibility"]["min_impressions"])
    effective_floor = configured_floor if min_impressions is None else int(min_impressions)
    root = safe_output(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    patterns = build_patterns(joined_rows, settings=settings)
    eligible = _eligible(joined_rows, effective_floor, settings)
    winners, losers = _split_by_category_median(eligible, patterns)

    reports = {
        "pattern_summary.json": patterns,
        "winner_loser_why.json": build_why_report(patterns),
        "text_psychology_all.json": summarize_psychology(eligible),
        "winner_text_psychology.json": summarize_psychology(winners),
        "loser_text_psychology.json": summarize_psychology(losers),
        "text_pattern_performance.json": compare_text_patterns(eligible, effective_floor),
        "next_ideas_from_winners.json": build_next_idea_rules(winners),
        "suggestion_for_loser.json": build_loser_suggestions(losers, winners),
    }
    for name, payload in reports.items():
        (root / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"output_dir": str(root), "winner_rows": len(winners), "loser_rows": len(losers), "winner_records": winners, "loser_records": losers, "reports": list(reports)}

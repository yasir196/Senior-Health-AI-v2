from __future__ import annotations

from pathlib import Path
from typing import Any

from analytics_db import (
    build_thumbnail_packaging_comparisons,
    join_all_thumbnail_ctr_evidence,
    sync_packaging_rule_candidates,
    write_active_packaging_rules_file,
)
from thumbnail_analysis import analyze_pending_thumbnails
from thumbnail_assets import refresh_channel_thumbnails


def auto_sync_thumbnail_learning(
    db_path: Path,
    active_rules_path: Path,
    *,
    model: str | None = None,
) -> dict[str, Any]:
    """Run the full thumbnail-learning refresh after a YouTube analytics sync.

    The user does not have to run archive/vision/join/comparison/candidate stages.
    Each phase is best-effort so an unavailable CTR window or vision/API problem
    does not turn an otherwise successful YouTube sync into a failure.
    """
    result: dict[str, Any] = {
        "thumbnails": {},
        "analysis": {},
        "ctr_join": {},
        "comparisons": {},
        "candidates": {},
        "active_rules": {},
        "warnings": [],
    }

    try:
        result["thumbnails"] = refresh_channel_thumbnails(db_path)
    except Exception as exc:
        result["warnings"].append(f"Thumbnail refresh: {exc}")

    try:
        result["analysis"] = analyze_pending_thumbnails(db_path, model=model)
    except Exception as exc:
        result["warnings"].append(f"Thumbnail vision analysis: {exc}")

    try:
        result["ctr_join"] = join_all_thumbnail_ctr_evidence(db_path)
    except Exception as exc:
        result["warnings"].append(f"CTR evidence join: {exc}")

    try:
        result["comparisons"] = build_thumbnail_packaging_comparisons(db_path)
    except Exception as exc:
        # This is expected on young channels / newly changed thumbnails with no
        # attributable post-snapshot CTR yet, so keep it as a diagnostic warning.
        result["warnings"].append(f"Packaging comparison refresh: {exc}")

    try:
        result["candidates"] = sync_packaging_rule_candidates(db_path)
    except Exception as exc:
        result["warnings"].append(f"Packaging candidate refresh: {exc}")

    try:
        result["active_rules"] = write_active_packaging_rules_file(db_path, active_rules_path)
    except Exception as exc:
        result["warnings"].append(f"Active packaging rules file: {exc}")

    return result

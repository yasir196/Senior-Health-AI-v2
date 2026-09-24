from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .explain import build_why_report


def export_pattern_files(patterns: dict[str, Any], output_root: Path) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    payloads = {
        "winner_patterns.json": patterns["winner_patterns"],
        "loser_patterns.json": patterns["loser_patterns"],
        "category_patterns.json": patterns["category_patterns"],
        "winner_loser_why.json": build_why_report(patterns),
        "thumbnail_rules.json": {
            "status": "observational",
            "method": patterns["method"],
            "eligible_observations": patterns["eligible_observations"],
            "note": "Rules must be derived from repeated, adequately sampled channel observations; no generic AI score is used."
        },
        "analysis_manifest.json": {
            "schema_version": patterns["schema_version"],
            "eligible_observations": patterns["eligible_observations"],
            "excluded_observations": patterns["excluded_observations"],
            "method": patterns["method"],
        },
    }
    for filename, payload in payloads.items():
        (output_root / filename).write_text(json.dumps(payload, indent=2), encoding="utf-8")

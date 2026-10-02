from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from production_rules import enabled_rules
from production_timing_controller import _seconds, resolve_rule

TIMELINE_FILE = "08_ratio_allocated_slots.csv"
REPORT_FILE = "timeline_qa_report.json"


def audit_timeline(project: Path) -> dict[str, Any]:
    project = Path(project)
    path = project / TIMELINE_FILE
    if not path.is_file():
        raise FileNotFoundError(f"{TIMELINE_FILE} is required for Timeline QA.")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{TIMELINE_FILE} has no slots.")

    rules = enabled_rules(project)
    issues: list[dict[str, Any]] = []
    previous_end: float | None = None
    total_duration = 0.0

    for index, row in enumerate(rows, 1):
        slot = str(row.get("slot_id") or f"row {index}")
        start = _seconds(row.get("start_time", "0"))
        end = _seconds(row.get("end_time", "0"))
        duration = float(row.get("duration_sec", 0) or 0)
        scope = str(row.get("scope") or "BODY").upper()
        total_duration += max(0.0, duration)

        if end <= start:
            issues.append({"severity":"HARD","type":"INVALID_DURATION","slot_id":slot,"message":f"end {end:.3f}s must be after start {start:.3f}s"})
        calculated = end - start
        if abs(calculated - duration) > 0.002:
            issues.append({"severity":"HARD","type":"DURATION_MISMATCH","slot_id":slot,"message":f"stored {duration:.3f}s vs timestamp {calculated:.3f}s"})

        if previous_end is not None:
            delta = start - previous_end
            if delta > 0.002:
                issues.append({"severity":"HARD","type":"GAP","slot_id":slot,"message":f"{delta:.3f}s gap before slot"})
            elif delta < -0.002:
                issues.append({"severity":"HARD","type":"OVERLAP","slot_id":slot,"message":f"{abs(delta):.3f}s overlap before slot"})
        previous_end = end

        # Category-specific duration rules apply only when that asset category
        # was actually selected. An IMAGE rule must never imply IMAGE selection.
        asset_type = str(row.get("recommended_asset_type") or "").strip().upper()
        category = "IMAGE" if asset_type == "AI_IMAGE" else asset_type
        rule = resolve_rule(rules, scope, category) if category else None
        if rule:
            minimum = float(rule["min_seconds"])
            maximum = float(rule["max_seconds"])
            severity = "HARD" if rule["hard"] else "SOFT"
            if maximum > 0 and duration > maximum + 0.002:
                issues.append({"severity":severity,"type":"RULE_MAX","slot_id":slot,"rule_id":rule["id"],"message":f"{duration:.3f}s exceeds max {maximum:.3f}s"})
            if minimum > 0 and duration < minimum - 0.002:
                issues.append({"severity":severity,"type":"RULE_MIN","slot_id":slot,"rule_id":rule["id"],"message":f"{duration:.3f}s below min {minimum:.3f}s"})

    hard = [issue for issue in issues if issue["severity"] == "HARD"]
    soft = [issue for issue in issues if issue["severity"] == "SOFT"]
    report = {
        "status": "PASS" if not hard else "FAIL",
        "timeline_file": TIMELINE_FILE,
        "slot_count": len(rows),
        "total_slot_duration_seconds": round(total_duration, 3),
        "hard_issue_count": len(hard),
        "soft_warning_count": len(soft),
        "issues": issues,
    }
    (project / REPORT_FILE).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    return report

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from production_rules import enabled_rules
from production_timing_controller import resolve_rule

LANES = ("avatar", "ai_images", "stock", "overlays")
ASSET_BY_LANE = {
    "avatar": "AVATAR",
    "ai_images": "AI_IMAGE",
    "stock": "STOCK_VIDEO",
    "overlays": "OVERLAY",
}


def _load_settings(project: Path) -> dict[str, Any]:
    path = Path(project) / "production_settings.json"
    if not path.is_file():
        raise FileNotFoundError("production_settings.json is required.")
    return json.loads(path.read_text(encoding="utf-8"))


def _targets(settings: dict[str, Any]) -> dict[str, float]:
    values = {lane: float(settings.get(lane, 0) or 0) for lane in LANES}
    total = sum(values.values())
    if abs(total - 100.0) > 0.001:
        raise ValueError(f"Production Mix must total 100%, got {total:g}%.")
    return values


def validate_ratio_result(summary: dict[str, Any], *, tolerance_points: float, strict: bool) -> list[str]:
    """Validate actual duration shares against the user's GUI policy."""
    issues: list[str] = []
    allowed = 0.01 if strict else max(0.0, float(tolerance_points))
    for lane, values in summary.get("targets", {}).items():
        target = float(values.get("target_percent", 0) or 0)
        actual = float(values.get("actual_percent", 0) or 0)
        if target <= 0 and actual <= 0:
            continue
        delta = abs(actual - target)
        if delta > allowed + 1e-9:
            mode = "STRICT" if strict else f"±{allowed:g} percentage points"
            issues.append(
                f"{lane}: actual {actual:.3f}% vs target {target:.3f}% "
                f"(difference {delta:.3f} points) exceeds {mode}."
            )
    return issues


def allocate_ratio_targets(project: Path) -> Path:
    """Assign each deterministic slot to the user's production mix by duration.

    Allocation is duration-weighted, not scene-count weighted. For each slot choose
    the active lane with the largest remaining duration deficit. This keeps the
    user's GUI mix authoritative while preserving timestamp boundaries.
    """
    project = Path(project)
    slots_path = project / "08_production_slots.csv"
    if not slots_path.is_file():
        raise FileNotFoundError("08_production_slots.csv is required before ratio allocation.")
    settings = _load_settings(project)
    targets = _targets(settings)

    with slots_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    if not rows:
        raise ValueError("08_production_slots.csv has no slots.")

    total_duration = sum(float(row.get("duration_sec", 0) or 0) for row in rows)
    target_seconds = {lane: total_duration * pct / 100.0 for lane, pct in targets.items()}
    assigned_seconds = {lane: 0.0 for lane in LANES}
    active = [lane for lane in LANES if targets[lane] > 0]
    if not active:
        raise ValueError("At least one Production Mix lane must be greater than 0%.")

    rules = enabled_rules(project)
    for row in rows:
        duration = float(row.get("duration_sec", 0) or 0)
        scope = str(row.get("scope") or "BODY").upper()
        eligible = list(active)
        image_rule = resolve_rule(rules, scope, "IMAGE")
        if "ai_images" in eligible and image_rule:
            minimum = float(image_rule["min_seconds"])
            maximum = float(image_rule["max_seconds"])
            if (minimum > 0 and duration < minimum - 0.002) or (maximum > 0 and duration > maximum + 0.002):
                eligible.remove("ai_images")
        if not eligible:
            eligible = ["avatar"] if "avatar" in active else list(active)
        # Keep the requested mix distributed across the whole timeline while
        # respecting category eligibility. A short/long neutral window cannot be
        # labeled AI_IMAGE merely to hit a ratio target.
        lane = min(
            eligible,
            key=lambda name: (
                assigned_seconds[name] / target_seconds[name] if target_seconds[name] > 0 else float("inf"),
                LANES.index(name),
            ),
        )
        assigned_seconds[lane] += duration
        row["target_lane"] = lane
        row["recommended_asset_type"] = ASSET_BY_LANE[lane]
        row["ratio_target_percent"] = f"{targets[lane]:.2f}"
        row["ratio_target_seconds"] = f"{target_seconds[lane]:.3f}"
        row["ratio_assignment_source"] = "GUI_DURATION_MIX"

    out_fields = fields + [
        "target_lane", "recommended_asset_type", "ratio_target_percent",
        "ratio_target_seconds", "ratio_assignment_source",
    ]
    target = project / "08_ratio_allocated_slots.csv"
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=out_fields)
        writer.writeheader()
        writer.writerows(rows)

    strict = bool(settings.get("ratio_strict_mode", False))
    tolerance = float(settings.get("ratio_tolerance_points", 5.0) or 0.0)
    summary = {
        "total_duration_seconds": round(total_duration, 3),
        "ratio_policy": {
            "strict": strict,
            "tolerance_points": tolerance,
        },
        "targets": {
            lane: {
                "target_percent": targets[lane],
                "target_seconds": round(target_seconds[lane], 3),
                "assigned_seconds": round(assigned_seconds[lane], 3),
                "actual_percent": round((assigned_seconds[lane] / total_duration * 100.0) if total_duration else 0.0, 3),
            }
            for lane in LANES
        },
    }
    issues = validate_ratio_result(summary, tolerance_points=tolerance, strict=strict)
    summary["validation"] = {
        "status": "PASS" if not issues else "FAIL",
        "issues": issues,
    }
    (project / "production_ratio_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return target

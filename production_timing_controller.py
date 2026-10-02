from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from production_rules import enabled_rules

MASTER_TIMELINE = "08_master_narration_timeline.csv"
SLOT_TIMELINE = "08_production_slots.csv"

SLOT_COLUMNS = [
    "slot_id", "start_time", "end_time", "duration_sec", "scope",
    "source_segment_ids", "transcript_text", "rule_id", "rule_priority",
    "constraint_type", "timing_source",
]


def _seconds(value: str) -> float:
    value = str(value or "").strip()
    parts = value.split(":")
    if len(parts) == 2:
        return float(parts[0]) * 60 + float(parts[1])
    if len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    return float(value)


def _stamp(seconds: float) -> str:
    ms = max(0, round(seconds * 1000))
    minutes, rem = divmod(ms, 60000)
    sec, milli = divmod(rem, 1000)
    return f"{minutes}:{sec:02d}.{milli:03d}"


SECTION_SCOPES = ("HOOK", "EVIDENCE", "CTA", "BODY")


def _text_scope(text: str) -> str | None:
    """Recognize explicit section markers when upstream narration/timeline carries them."""
    value = str(text or "").upper()
    for scope in ("EVIDENCE", "CTA", "HOOK"):
        if re.search(rf"\b(?:SECTION|SCOPE|PURPOSE)\s*[:=\-]?\s*{scope}\b", value):
            return scope
    return None


def resolve_scope(row: dict[str, str], start: float, config: dict[str, Any]) -> str:
    explicit = str(row.get("scope") or row.get("Section") or row.get("section") or "").strip().upper()
    if explicit in SECTION_SCOPES:
        return explicit
    marked = _text_scope(row.get("Transcript Text", ""))
    if marked:
        return marked
    hook_end = float(config.get("production_hook_end_seconds", 30.0))
    return "HOOK" if start < hook_end else "BODY"


def resolve_rule(rules: list[dict[str, Any]], scope: str, category: str = "IMAGE") -> dict[str, Any] | None:
    """Resolve deterministic section override.

    Exact section rules beat ALL-scope fallback rules. Within the same specificity,
    enabled_rules() ordering makes higher priority win, then stable rule id.
    """
    candidates = [rule for rule in rules if rule["category"] == category and rule["scope"] in {scope, "ALL"}]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda rule: (0 if rule["scope"] == scope else 1, -int(rule["priority"]), rule["id"]),
    )[0]


def _split_interval(start: float, end: float, minimum: float, maximum: float) -> list[tuple[float, float]]:
    """Split an actual narration interval without inventing time.

    Boundaries remain inside the real transcript interval. Maximum is hard when
    configured. Minimum is a target: the final remainder is merged backward when
    possible so tiny artificial slots are not created.
    """
    duration = end - start
    if duration <= 0:
        return []
    if maximum <= 0 or duration <= maximum:
        return [(start, end)]
    count = max(1, int((duration + maximum - 1e-9) // maximum))
    while count > 1 and minimum > 0 and duration / count < minimum:
        count -= 1
    if duration / count > maximum + 1e-9:
        count += 1
    step = duration / count
    return [(start + i * step, end if i == count - 1 else start + (i + 1) * step) for i in range(count)]


def _group_scope_rows(rows: list[dict[str, str]], config: dict[str, Any]) -> list[tuple[str, list[dict[str, str]]]]:
    groups: list[tuple[str, list[dict[str, str]]]] = []
    current_scope: str | None = None
    current: list[dict[str, str]] = []
    previous_end: float | None = None
    for row in rows:
        start = _seconds(row.get("Actual Audio Start", "0"))
        end = _seconds(row.get("Actual Audio End", "0"))
        scope = resolve_scope(row, start, config)
        # Visual coverage continues through natural ASR pauses; transcript segment
        # gaps are not visual gaps and must not fragment the production timeline.
        if current and scope != current_scope:
            groups.append((str(current_scope), current))
            current = []
        current_scope = scope
        current.append(row)
        previous_end = end
    if current:
        groups.append((str(current_scope), current))
    return groups


def _partition_real_interval(start: float, end: float, minimum: float, maximum: float) -> list[tuple[float, float]]:
    """Partition one continuous real narration range into rule-compatible candidates.

    Boundaries may fall inside ASR segments because ASR segmentation is not a visual
    boundary authority. The range itself is never stretched, shortened, or moved.
    """
    duration = end - start
    if duration <= 0:
        return []
    if maximum <= 0 or minimum <= 0:
        return [(start, end)]
    min_count = max(1, int((duration + maximum - 1e-9) // maximum))
    max_count = max(1, int(duration // minimum))
    if min_count <= max_count:
        count = min_count
        step = duration / count
        return [(start + i * step, end if i == count - 1 else start + (i + 1) * step) for i in range(count)]
    # If the whole range cannot be divided into all-valid IMAGE windows, emit
    # max-sized neutral windows plus a real remainder. Downstream allocation may
    # assign the remainder to AVATAR; IMAGE eligibility is enforced there.
    intervals: list[tuple[float, float]] = []
    cursor = start
    while end - cursor > maximum + 1e-9:
        intervals.append((cursor, cursor + maximum))
        cursor += maximum
    if end - cursor > 1e-9:
        intervals.append((cursor, end))
    return intervals


def _rows_overlapping(rows: list[dict[str, str]], start: float, end: float) -> list[dict[str, str]]:
    return [row for row in rows if _seconds(row.get("Actual Audio End", "0")) > start + 1e-9 and _seconds(row.get("Actual Audio Start", "0")) < end - 1e-9]

def build_production_slots(project: Path, config: dict[str, Any]) -> Path:
    project = Path(project)
    source = project / MASTER_TIMELINE
    if not source.is_file():
        raise FileNotFoundError(f"{MASTER_TIMELINE} is required before production slot timing.")
    with source.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{MASTER_TIMELINE} has no timestamped narration rows.")

    rules = enabled_rules(project)
    out: list[dict[str, str]] = []
    slot_no = 0
    for scope, scope_rows in _group_scope_rows(rows, config):
        # Duration rules shape neutral visual candidate windows only. They never
        # choose the asset category; ratio/AI selection happens downstream.
        rule = resolve_rule(rules, scope, "IMAGE")
        minimum = float(rule["min_seconds"]) if rule else 0.0
        maximum = float(rule["max_seconds"]) if rule else 0.0
        group_start = _seconds(scope_rows[0].get("Actual Audio Start", "0"))
        group_end = _seconds(scope_rows[-1].get("Actual Audio End", "0"))
        intervals = _partition_real_interval(group_start, group_end, minimum, maximum) if rule else [(group_start, group_end)]
        for part_start, part_end in intervals:
            covered = _rows_overlapping(scope_rows, part_start, part_end)
            slot_no += 1
            ids = "|".join(str(row.get("Segment ID") or "") for row in covered)
            text = " ".join(str(row.get("Transcript Text") or "").strip() for row in covered).strip()
            out.append({
                "slot_id": f"P{slot_no:04d}", "start_time": _stamp(part_start), "end_time": _stamp(part_end),
                "duration_sec": f"{part_end - part_start:.3f}", "scope": scope,
                "source_segment_ids": ids, "transcript_text": text,
                "rule_id": str(rule["id"] if rule else ""), "rule_priority": str(rule["priority"] if rule else ""),
                "constraint_type": "HARD" if rule and rule["hard"] else ("SOFT" if rule else "NONE"),
                "timing_source": "MASTER_TRANSCRIPT",
            })
    target = project / SLOT_TIMELINE
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SLOT_COLUMNS); writer.writeheader(); writer.writerows(out)
    return target


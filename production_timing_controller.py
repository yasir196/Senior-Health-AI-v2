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
        contiguous = previous_end is None or abs(start - previous_end) <= 0.002
        if current and (scope != current_scope or not contiguous):
            groups.append((str(current_scope), current))
            current = []
        current_scope = scope
        current.append(row)
        previous_end = end
    if current:
        groups.append((str(current_scope), current))
    return groups


def _aggregate_rows(rows: list[dict[str, str]], minimum: float, maximum: float) -> list[list[dict[str, str]]]:
    """Aggregate adjacent real transcript segments into visual candidate slots.

    No audio time is invented. A group closes once it reaches the rule minimum;
    a segment that would push the group past max starts the next group. Short final
    remainders merge backward when the combined duration still fits max.
    """
    if not rows:
        return []
    if maximum <= 0:
        return [[row] for row in rows]
    groups: list[list[dict[str, str]]] = []
    current: list[dict[str, str]] = []
    for row in rows:
        if not current:
            current = [row]
            continue
        cur_start = _seconds(current[0].get("Actual Audio Start", "0"))
        row_end = _seconds(row.get("Actual Audio End", "0"))
        cur_end = _seconds(current[-1].get("Actual Audio End", "0"))
        cur_duration = cur_end - cur_start
        combined = row_end - cur_start
        if cur_duration >= minimum > 0 or combined > maximum + 0.002:
            groups.append(current)
            current = [row]
        else:
            current.append(row)
    if current:
        groups.append(current)
    if len(groups) > 1 and minimum > 0:
        last = groups[-1]
        last_duration = _seconds(last[-1].get("Actual Audio End", "0")) - _seconds(last[0].get("Actual Audio Start", "0"))
        merged_duration = _seconds(last[-1].get("Actual Audio End", "0")) - _seconds(groups[-2][0].get("Actual Audio Start", "0"))
        if last_duration < minimum - 0.002 and merged_duration <= maximum + 0.002:
            groups[-2].extend(groups.pop())
    return groups


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
        # IMAGE rules define constraints for an image *if AI later selects one*.
        # They do not force this section or slot to become an image.
        rule = resolve_rule(rules, scope, "IMAGE")
        minimum = float(rule["min_seconds"]) if rule else 0.0
        maximum = float(rule["max_seconds"]) if rule else 0.0
        candidates = _aggregate_rows(scope_rows, minimum, maximum) if rule else [[row] for row in scope_rows]
        for candidate in candidates:
            start = _seconds(candidate[0].get("Actual Audio Start", "0"))
            end = _seconds(candidate[-1].get("Actual Audio End", "0"))
            # A single ASR segment can exceed the visual max. Split only that real
            # interval; transcript text remains descriptive, timing remains actual.
            intervals = _split_interval(start, end, minimum, maximum) if maximum > 0 else [(start, end)]
            ids = "|".join(str(row.get("Segment ID") or "") for row in candidate)
            text = " ".join(str(row.get("Transcript Text") or "").strip() for row in candidate).strip()
            for part_start, part_end in intervals:
                slot_no += 1
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


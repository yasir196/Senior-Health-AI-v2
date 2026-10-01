from __future__ import annotations

import csv
from pathlib import Path

TIMING_FIELDS = ("start_time", "end_time", "duration_sec")
LOCKED_SLOTS = "08_ratio_allocated_slots.csv"


def _clean(value: object) -> str:
    return str(value or "").strip()


def load_locked_slots(project: Path) -> list[dict[str, str]]:
    path = Path(project) / LOCKED_SLOTS
    if not path.is_file():
        raise FileNotFoundError(f"{LOCKED_SLOTS} is required before AI visual planning.")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{LOCKED_SLOTS} has no deterministic timestamp slots.")
    return rows


def validate_ai_timing_lock(project: Path, production_rows: list[dict[str, str]]) -> list[str]:
    """Reject any Production output that changes Python-owned timing.

    AI may choose visual planning fields only. start/end/duration must be copied
    exactly from the deterministic timestamp/ratio slot ledger.
    """
    slots = load_locked_slots(project)
    issues: list[str] = []
    if len(production_rows) != len(slots):
        return [
            f"Production row count {len(production_rows)} does not match locked slot count {len(slots)}; "
            "AI may not split, merge, add, or remove timestamp slots."
        ]

    for index, (slot, row) in enumerate(zip(slots, production_rows), 1):
        sid = _clean(slot.get("slot_id")) or f"slot {index}"
        for field in TIMING_FIELDS:
            expected = _clean(slot.get(field))
            actual = _clean(row.get(field))
            if actual != expected:
                issues.append(
                    f"{sid}: {field} is locked to {expected!r}; Production output supplied {actual!r}."
                )
        expected_text = _clean(slot.get("transcript_text"))
        actual_text = _clean(row.get("script_excerpt"))
        if expected_text and actual_text != expected_text:
            issues.append(f"{sid}: script_excerpt must copy the locked slot transcript text exactly.")
    return issues

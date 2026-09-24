from __future__ import annotations
from copy import deepcopy
from typing import Any

from .schema import ALLOWED_FLAGS


def apply_human_review(record: dict[str, Any], *, flags: list[str], corrections: dict[str, Any] | None = None, notes: str = "") -> dict[str, Any]:
    invalid = sorted(set(flags) - set(ALLOWED_FLAGS))
    if invalid:
        raise ValueError(f"Unsupported review flags: {invalid}")
    updated = deepcopy(record)
    updated["human_review"] = {
        "status": "reviewed",
        "flags": list(dict.fromkeys(flags)),
        "corrections": corrections or {},
        "notes": notes,
    }
    return updated


def effective_view(record: dict[str, Any]) -> dict[str, Any]:
    """AI-consumable view: preserve raw evidence and expose corrections separately."""
    return {
        "observed": record["observed"],
        "inferred": record["inferred"],
        "human_review": record["human_review"],
        "use_human_corrections_for_future_learning": record["human_review"]["status"] == "reviewed",
    }

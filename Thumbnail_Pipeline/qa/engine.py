from __future__ import annotations

from copy import deepcopy
from typing import Any

REVIEWABLE_FIELDS = ("layout", "subject_placement", "text_placement", "safe_zone")
_REQUIRED_FOR_RENDER = set(REVIEWABLE_FIELDS)


def apply_composition_review(
    composition_spec: dict[str, Any],
    *,
    corrections: dict[str, Any],
    notes: str = "",
) -> dict[str, Any]:
    """Apply explicit human composition decisions without changing evidence provenance."""
    unknown = sorted(set(corrections) - set(REVIEWABLE_FIELDS))
    if unknown:
        raise ValueError(f"Unsupported composition review fields: {unknown}")

    updated = deepcopy(composition_spec)
    composition = updated.setdefault("composition", {})
    for field, value in corrections.items():
        if value not in (None, ""):
            composition[field] = value

    unresolved = [field for field in REVIEWABLE_FIELDS if composition.get(field) in (None, "")]
    updated["human_review_required_for"] = unresolved
    updated["human_review"] = {
        "status": "reviewed",
        "corrections": deepcopy(corrections),
        "notes": notes,
    }
    updated["status"] = "review_complete" if not unresolved else "needs_human_direction"
    # Review completion does not itself enable rendering; the explicit gate below does.
    updated.setdefault("constraints", {})["generation_allowed"] = False
    updated["constraints"]["renderer_allowed"] = False
    return updated


def evaluate_generation_gate(composition_spec: dict[str, Any]) -> dict[str, Any]:
    """Evaluate, but do not execute, the Phase 4 generation gate."""
    composition = composition_spec.get("composition") or {}
    unresolved = [
        field for field in REVIEWABLE_FIELDS
        if field in _REQUIRED_FOR_RENDER and composition.get(field) in (None, "")
    ]
    title_locked = bool((composition_spec.get("constraints") or {}).get("title_must_remain_unchanged", True))
    review_complete = not unresolved
    approved = bool(review_complete and title_locked)
    return {
        "schema_version": "0.4.0",
        "approved": approved,
        "immutable_title": composition_spec.get("immutable_title") or "",
        "unresolved_fields": unresolved,
        "checks": {
            "human_review_complete": review_complete,
            "immutable_title_lock_active": title_locked,
        },
        "renderer_invoked": False,
        "instruction": (
            "Approved for a later renderer handoff; this gate does not render."
            if approved
            else "Resolve required composition fields before renderer handoff."
        ),
    }

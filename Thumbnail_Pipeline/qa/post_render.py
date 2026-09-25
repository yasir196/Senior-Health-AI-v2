from __future__ import annotations

from copy import deepcopy
from typing import Any

_REQUIRED_ASSET_FIELDS = ("output_path", "width", "height")
_REQUIRED_CONTRACT_FIELDS = ("layout", "subject_placement", "text_placement", "safe_zone")


def evaluate_post_render_qa(
    artifact: dict[str, Any],
    *,
    observed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate a rendered artifact without inventing observations.

    Structural contract checks are automatic. Visual/composition checks remain
    pending unless an analyzer or human review explicitly supplies observations.
    """
    asset = artifact.get("asset") or {}
    contract = artifact.get("render_contract") or {}
    observed = deepcopy(observed or {})

    structural_failures = [
        field for field in _REQUIRED_ASSET_FIELDS if asset.get(field) in (None, "", 0)
    ]
    contract_failures = [
        field for field in _REQUIRED_CONTRACT_FIELDS if contract.get(field) in (None, "")
    ]

    visual_checks = {}
    for key in ("layout_matches", "subject_placement_matches", "text_placement_matches", "safe_zone_clear"):
        value = observed.get(key)
        visual_checks[key] = value if isinstance(value, bool) else None

    explicit_visual_failures = [key for key, value in visual_checks.items() if value is False]
    pending_visual_checks = [key for key, value in visual_checks.items() if value is None]

    if structural_failures or contract_failures or explicit_visual_failures:
        status = "failed"
    elif pending_visual_checks:
        status = "needs_human_review"
    else:
        status = "passed"

    return {
        "schema_version": "0.7.0",
        "status": status,
        "immutable_title": artifact.get("immutable_title") or "",
        "checks": {
            "structural_failures": structural_failures,
            "contract_failures": contract_failures,
            "visual": visual_checks,
        },
        "human_review_required_for": pending_visual_checks,
        "final_asset_accepted": status == "passed",
    }


def apply_post_render_review(
    artifact: dict[str, Any],
    qa_result: dict[str, Any],
    *,
    decisions: dict[str, bool],
    notes: str = "",
) -> dict[str, Any]:
    """Resolve only pending visual QA fields, then re-evaluate final acceptance."""
    allowed = set(qa_result.get("human_review_required_for") or [])
    unknown = sorted(set(decisions) - allowed)
    if unknown:
        raise ValueError(f"Review may only resolve pending QA fields: {unknown}")
    if any(not isinstance(value, bool) for value in decisions.values()):
        raise ValueError("Post-render QA decisions must be boolean.")

    observed = dict((qa_result.get("checks") or {}).get("visual") or {})
    observed.update(decisions)
    reviewed = evaluate_post_render_qa(artifact, observed=observed)
    reviewed["human_review"] = {"status": "reviewed", "decisions": deepcopy(decisions), "notes": notes}
    return reviewed

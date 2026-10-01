from __future__ import annotations

from typing import Any


def _clean_examples(concept_direction: dict[str, Any]) -> list[str]:
    concept = concept_direction.get("concept") or {}
    return [
        str(x).strip()
        for x in (concept.get("thumbnail_text_examples") or [])
        if str(x).strip()
    ]


def build_composition_spec(concept_direction: dict[str, Any]) -> dict[str, Any]:
    """Convert a Phase 2 concept direction into a render-neutral composition contract.

    The contract is deliberately evidence-bound: it preserves the immutable title,
    carries supported layout/text evidence forward, and leaves unsupported visual
    decisions unset for human review rather than inventing defaults.
    """
    concept = concept_direction.get("concept") or {}
    evidence = concept_direction.get("evidence") or {}
    constraints = concept_direction.get("constraints") or {}
    examples = _clean_examples(concept_direction)
    layout = concept.get("composition_layout")
    supported = concept_direction.get("evidence_status") in ("winner_supported", "association_supported")
    subject_placement = concept.get("presenter_position")
    # Text placement can be derived only when the observed layout explicitly encodes it.
    layout_lower = str(layout or "").lower()
    text_placement = "left" if ("text_left" in layout_lower or layout_lower.startswith("left_")) else ("right" if "text_right" in layout_lower else None)
    # Safe zone is a deterministic rendering/platform constraint, not winner/CTR evidence.
    # Keep it independent from text/subject placement: the bottom-right timestamp cell
    # must remain free of critical text/action in every composition.
    safe_zone = "bottom-right timestamp-safe area clear"

    return {
        "schema_version": "0.3.0",
        "immutable_title": str(concept_direction.get("immutable_title") or ""),
        "category": concept.get("category"),
        "status": "ready_for_prompt_review" if supported else "needs_human_direction",
        "composition": {
            "layout": layout,
            "thumbnail_text_candidates": examples[:5],
            "subject_placement": subject_placement,
            "text_placement": text_placement,
            "safe_zone": safe_zone,
        },
        "provenance": {
            "source": "phase2_concept_direction",
            "channel_winner_count": int(evidence.get("channel_winner_count") or 0),
            "youtube_reference_count": int(evidence.get("youtube_reference_count") or 0),
            "layout_supported_by_winner_evidence": bool(layout and supported),
            "text_candidates_supported_by_winner_evidence": bool(examples and supported),
            "subject_placement_supported_by_association_evidence": bool(subject_placement),
            "text_placement_derived_from_layout": bool(text_placement),
            "safe_zone_source": "render_contract",
        },
        "constraints": {
            "title_must_remain_unchanged": constraints.get("title_must_remain_unchanged", True),
            "external_references_are_secondary": constraints.get("external_references_are_secondary", True),
            "losers_may_seed_new_concept": False,
            "generation_allowed": False,
            "renderer_allowed": False,
        },
        "human_review_required_for": [
            key
            for key, value in {
                "layout": layout,
                "subject_placement": subject_placement,
                "text_placement": text_placement,
                "safe_zone": safe_zone,
            }.items()
            if value is None
        ],
    }


def build_prompt_spec(composition_spec: dict[str, Any]) -> dict[str, Any]:
    """Create a structured prompt handoff without enabling generation."""
    composition = composition_spec.get("composition") or {}
    return {
        "schema_version": "0.3.0",
        "immutable_title": composition_spec.get("immutable_title") or "",
        "status": composition_spec.get("status"),
        "prompt_contract": {
            "layout": composition.get("layout"),
            "thumbnail_text_candidates": composition.get("thumbnail_text_candidates") or [],
            "subject_placement": composition.get("subject_placement"),
            "text_placement": composition.get("text_placement"),
            "safe_zone": composition.get("safe_zone"),
        },
        "human_review_required_for": list(composition_spec.get("human_review_required_for") or []),
        "generation_allowed": False,
        "instruction": "Do not render until required human-review fields are resolved and a later generation gate explicitly enables rendering.",
    }

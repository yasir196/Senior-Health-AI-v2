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

    return {
        "schema_version": "0.3.0",
        "immutable_title": str(concept_direction.get("immutable_title") or ""),
        "category": concept.get("category"),
        "status": "ready_for_prompt_review" if supported else "needs_human_direction",
        "composition": {
            "layout": layout,
            "thumbnail_text_candidates": examples[:5],
            "subject_placement": subject_placement,
            "text_placement": None,
            "safe_zone": None,
        },
        "provenance": {
            "source": "phase2_concept_direction",
            "channel_winner_count": int(evidence.get("channel_winner_count") or 0),
            "youtube_reference_count": int(evidence.get("youtube_reference_count") or 0),
            "layout_supported_by_winner_evidence": bool(layout and supported),
            "text_candidates_supported_by_winner_evidence": bool(examples and supported),
            "subject_placement_supported_by_association_evidence": bool(subject_placement),
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
                "text_placement": None,
                "safe_zone": None,
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

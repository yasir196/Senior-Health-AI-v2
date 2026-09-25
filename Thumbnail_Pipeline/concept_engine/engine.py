from __future__ import annotations

from collections import Counter
from typing import Any

from Thumbnail_Pipeline.intelligence.patterns import classify_category
from Thumbnail_Pipeline.intelligence.title_text_pair import pair_features


def _winner_evidence(context: dict[str, Any]) -> list[dict[str, Any]]:
    prior = context.get("winner_prior") or {}
    for key in ("winner_examples", "examples", "evidence"):
        value = prior.get(key)
        if isinstance(value, list):
            return value
    value = context.get("winner_examples")
    return value if isinstance(value, list) else []


def _reference_evidence(context: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("youtube_examples", "external_references", "references"):
        value = context.get(key)
        if isinstance(value, list):
            return value
    return []


def _mode(values: list[Any]) -> Any | None:
    clean = [v for v in values if v not in (None, "", [], {})]
    return Counter(clean).most_common(1)[0][0] if clean else None


def build_concept_direction(context: dict[str, Any]) -> dict[str, Any]:
    """Turn evidence context into a conservative, traceable concept brief.

    This stage does not generate a thumbnail and never rewrites the supplied title.
    Missing evidence stays missing rather than being replaced by generic thumbnail lore.
    """
    title = str(context.get("immutable_title") or "")
    requested_category = str(context.get("requested_category") or "uncategorized")
    winners = _winner_evidence(context)
    refs = _reference_evidence(context)

    winner_texts = [
        (r.get("thumbnail_text") if isinstance(r, dict) else None)
        or ((r.get("ocr") or {}).get("text") if isinstance(r, dict) else None)
        for r in winners
    ]
    layouts = [
        ((r.get("v2_analysis") or {}).get("composition_layout") if isinstance(r, dict) else None)
        or (r.get("composition_layout") if isinstance(r, dict) else None)
        for r in winners
    ]
    hero_categories = [
        classify_category(r) for r in winners if isinstance(r, dict)
    ]

    return {
        "schema_version": "0.2.0",
        "immutable_title": title,
        "requested_category": requested_category,
        "evidence_status": "winner_supported" if winners else "no_winner_evidence",
        "concept": {
            "category": _mode(hero_categories) or requested_category,
            "composition_layout": _mode(layouts),
            "thumbnail_text_examples": [t for t in winner_texts if t][:5],
            "title_text_relationship": [
                pair_features(title, t) for t in winner_texts if t
            ][:5],
        },
        "evidence": {
            "channel_winner_count": len(winners),
            "youtube_reference_count": len(refs),
            "channel_winners": winners[:10],
            "youtube_references": refs[:10],
        },
        "constraints": {
            "title_must_remain_unchanged": True,
            "losers_may_seed_new_concept": False,
            "external_references_are_secondary": True,
            "generation_allowed": False,
        },
        "notes": [
            "Observed winner evidence is a prior, not causal proof.",
            "Null concept fields mean the available evidence did not support a direction.",
        ],
    }

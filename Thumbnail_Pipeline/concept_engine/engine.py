from __future__ import annotations

from collections import Counter
from typing import Any

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
    for key in ("youtube_reference_examples", "youtube_examples", "external_references", "references"):
        value = context.get(key)
        if isinstance(value, list):
            return value
    return []


def _mode(values: list[Any]) -> Any | None:
    clean = [v for v in values if v not in (None, "", [], {})]
    return Counter(clean).most_common(1)[0][0] if clean else None


def _association_choice(rows: list[dict[str, Any]], feature: str) -> Any | None:
    """Prefer category evidence (caller order), then strongest supported association."""
    candidates = []
    for r in rows:
        if r.get("feature_name") != feature:
            continue
        direction = str(r.get("association_direction") or "").lower()
        if direction in {"negative", "lower"}:
            continue
        try:
            weight = float(r.get("evidence_weight") or 0)
            videos = int(r.get("video_count") or 0)
            impressions = float(r.get("total_impressions") or 0)
            delta = float(r.get("ctr_delta_points") or 0)
        except (TypeError, ValueError):
            continue
        candidates.append((weight, videos, impressions, delta, r.get("feature_value")))
    if not candidates:
        return None
    candidates.sort(reverse=True, key=lambda x: (x[0], x[1], x[2], x[3]))
    return candidates[0][4]


def build_concept_direction(context: dict[str, Any]) -> dict[str, Any]:
    """Turn evidence context into a conservative, traceable concept brief.

    This stage does not generate a thumbnail and never rewrites the supplied title.
    Missing evidence stays missing rather than being replaced by generic thumbnail lore.
    """
    title = str(context.get("immutable_title") or "")
    requested_category = str(context.get("requested_category") or "uncategorized")
    winners = _winner_evidence(context)
    refs = _reference_evidence(context)
    associations = context.get("packaging_associations") or {}
    category_associations = associations.get("category") or []
    channel_associations = associations.get("channel") or []

    winner_texts = [
        (r.get("thumbnail_text") if isinstance(r, dict) else None)
        or ((r.get("ocr") or {}).get("text") if isinstance(r, dict) else None)
        for r in winners
    ]
    layouts = [
        ((r.get("v2_analysis") or {}).get("composition_layout") if isinstance(r, dict) else None)
        or ((r.get("visual_analysis") or {}).get("composition_layout") if isinstance(r, dict) else None)
        or (r.get("composition_layout") if isinstance(r, dict) else None)
        for r in winners
    ]
    # Category lane is intentionally considered before channel-wide fallback.
    association_rows = category_associations or channel_associations
    association_layout = _association_choice(association_rows, "composition_layout")
    presenter_position = _association_choice(association_rows, "presenter_position")
    text_style = _association_choice(association_rows, "text_style")
    title_thumbnail_relationship = _association_choice(association_rows, "title_thumbnail_relationship")
    question_hook = _association_choice(association_rows, "question_hook")
    number_hook = _association_choice(association_rows, "number_hook")
    background_style = _association_choice(association_rows, "background_style")
    background_brightness = _association_choice(association_rows, "background_brightness")
    text_color_scheme = _association_choice(association_rows, "text_color_scheme")
    accent_color_family = _association_choice(association_rows, "accent_color_family")
    supported = bool(winners or category_associations or channel_associations)

    return {
        "schema_version": "0.2.0",
        "immutable_title": title,
        "requested_category": requested_category,
        "evidence_status": "winner_supported" if winners else ("association_supported" if supported else "no_winner_evidence"),
        "concept": {
            "category": requested_category,
            "composition_layout": _mode(layouts) or association_layout,
            "thumbnail_text_examples": [t for t in winner_texts if t][:5],
            "title_text_relationship": [pair_features(title, t) for t in winner_texts if t][:5],
            "presenter_position": presenter_position,
            "text_style": text_style,
            "title_thumbnail_relationship": title_thumbnail_relationship,
            "question_hook": question_hook,
            "number_hook": number_hook,
            "background_style": background_style,
            "background_brightness": background_brightness,
            "text_color_scheme": text_color_scheme,
            "accent_color_family": accent_color_family,
        },
        "evidence": {
            "channel_winner_count": len(winners),
            "youtube_reference_count": len(refs),
            "channel_winners": winners[:10],
            "youtube_references": refs[:10],
            "packaging_association_run": associations.get("run"),
            "cluster_associations": category_associations,
            "channel_associations": channel_associations,
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

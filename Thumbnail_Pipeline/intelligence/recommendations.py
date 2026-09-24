from __future__ import annotations

from typing import Any

from .title_text_pair import hook_type, pair_features


def build_next_idea_rules(winner_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Only winners are allowed to seed future concept directions."""
    examples = []
    for row in winner_rows:
        perf, ocr = row.get("performance") or {}, row.get("ocr") or {}
        examples.append({
            "title": perf.get("title"),
            "thumbnail_text": ocr.get("text"),
            "hook_type": hook_type(ocr.get("text")),
            "pair": pair_features(perf.get("title"), ocr.get("text")),
            "ctr": perf.get("ctr"),
            "impressions": perf.get("impressions"),
        })
    return {
        "policy": "future_ideas_seeded_from_winners_only",
        "winner_examples": examples,
        "instruction": "Use repeated winner title+thumbnail-text relationships as concept priors. Do not copy loser patterns into normal next-idea generation."
    }


def build_loser_suggestions(loser_rows: list[dict[str, Any]], winner_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Losers generate repair suggestions, never normal idea priors."""
    winner_hooks = sorted({hook_type((r.get("ocr") or {}).get("text")) for r in winner_rows})
    suggestions = []
    for row in loser_rows:
        perf, ocr = row.get("performance") or {}, row.get("ocr") or {}
        suggestions.append({
            "title": perf.get("title"),
            "loser_thumbnail_text": ocr.get("text"),
            "observed_hook_type": hook_type(ocr.get("text")),
            "title_text_pair": pair_features(perf.get("title"), ocr.get("text")),
            "suggestion_for_loser": {
                "test_against_winner_hook_types": winner_hooks,
                "instruction": "Keep the original title fixed. Create a fresh thumbnail-text/composition test using winner-supported patterns from the same category; do not simply recycle this loser's pattern."
            },
        })
    return {
        "policy": "losers_are_repair_inputs_not_future_idea_seeds",
        "suggestions": suggestions,
    }

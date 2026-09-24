from __future__ import annotations
from collections import defaultdict
from typing import Any
from .title_text_pair import hook_type, pair_features
from .patterns import classify_category

def build_next_idea_rules(winner_rows:list[dict[str,Any]])->dict[str,Any]:
    examples=[]
    for row in winner_rows:
        perf,ocr=row.get("performance") or {},row.get("ocr") or {}
        examples.append({"category":classify_category(row),"title":perf.get("title"),"thumbnail_text":ocr.get("text"),"hook_type":hook_type(ocr.get("text")),"pair":pair_features(perf.get("title"),ocr.get("text")),"ctr":perf.get("ctr"),"impressions":perf.get("impressions"),"evidence_weight":perf.get("evidence_weight")})
    return {"policy":"future_ideas_seeded_from_winners_only","winner_examples":examples,"instruction":"Use repeated winner title+thumbnail-text relationships as concept priors. Do not copy loser patterns into normal next-idea generation."}

def build_loser_suggestions(loser_rows:list[dict[str,Any]],winner_rows:list[dict[str,Any]])->dict[str,Any]:
    winners_by_category=defaultdict(list)
    for r in winner_rows: winners_by_category[classify_category(r)].append(r)
    suggestions=[]
    for row in loser_rows:
        perf,ocr=row.get("performance") or {},row.get("ocr") or {}; category=classify_category(row)
        peers=winners_by_category.get(category,[])
        winner_hooks=sorted({hook_type((r.get("ocr") or {}).get("text")) for r in peers})
        evidence=[{"title":(r.get("performance") or {}).get("title"),"thumbnail_text":(r.get("ocr") or {}).get("text"),"ctr":(r.get("performance") or {}).get("ctr"),"impressions":(r.get("performance") or {}).get("impressions"),"evidence_weight":(r.get("performance") or {}).get("evidence_weight")} for r in peers]
        suggestions.append({"category":category,"title":perf.get("title"),"loser_thumbnail_text":ocr.get("text"),"observed_hook_type":hook_type(ocr.get("text")),"title_text_pair":pair_features(perf.get("title"),ocr.get("text")),"suggestion_for_loser":{"same_category_winner_hook_types":winner_hooks,"same_category_winner_evidence":evidence,"instruction":"Keep the original title fixed. Repair only from same-category winner evidence. If no same-category winner evidence exists, do not invent a winner-supported pattern."}})
    return {"policy":"losers_are_repair_inputs_not_future_idea_seeds","suggestions":suggestions}

from __future__ import annotations
from typing import Any
from .patterns import classify_category

def build_new_project_prior(*,category:str,winner_rows:list[dict[str,Any]])->dict[str,Any]:
    peers=[r for r in winner_rows if classify_category(r)==category]
    if not peers:
        return {"status":"INSUFFICIENT_WINNER_EVIDENCE","category":category,"source_lane":"winners_only","winner_examples":[],"loser_fallback_allowed":False}
    examples=[]
    for r in peers:
        p,o,v=r.get("performance") or {},r.get("ocr") or {},r.get("v2_analysis") or {}
        examples.append({"title":p.get("title"),"thumbnail_text":o.get("text"),"ctr":p.get("ctr"),"impressions":p.get("impressions"),"evidence_weight":p.get("evidence_weight"),"visual_analysis":v})
    return {"status":"READY","category":category,"source_lane":"winners_only","winner_examples":examples,"loser_fallback_allowed":False,"instruction":"Use only these eligible same-category winner observations as learned thumbnail priors. Keep the new project's supplied title immutable. Do not import loser or loser-repair patterns."}

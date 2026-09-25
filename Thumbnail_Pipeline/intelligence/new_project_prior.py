from __future__ import annotations
from collections import defaultdict
from typing import Any
from .patterns import classify_category

def _num(v:Any,default:float=0.0)->float:
    try:return float(v)
    except (TypeError,ValueError):return default

def _category_strength(rows:list[dict[str,Any]])->list[dict[str,Any]]:
    groups=defaultdict(list)
    for r in rows: groups[classify_category(r)].append(r)
    ranked=[]
    for category,items in groups.items():
        total_imp=sum(_num((r.get("performance") or {}).get("impressions")) for r in items)
        if total_imp<=0: continue
        weighted_ctr=sum(_num((r.get("performance") or {}).get("ctr"))*_num((r.get("performance") or {}).get("impressions")) for r in items)/total_imp
        weights=[_num((r.get("performance") or {}).get("evidence_weight"),1.0) for r in items]
        avg_weight=sum(weights)/len(weights) if weights else 0.0
        # Ranking is evidence-derived: weighted CTR first, then evidence weight, impressions, observations.
        ranked.append({"category":category,"weighted_ctr":weighted_ctr,"average_evidence_weight":avg_weight,"total_impressions":total_imp,"winner_observations":len(items),"rows":items})
    return sorted(ranked,key=lambda x:(x["weighted_ctr"],x["average_evidence_weight"],x["total_impressions"],x["winner_observations"]),reverse=True)

def build_new_project_prior(*,category:str,winner_rows:list[dict[str,Any]])->dict[str,Any]:
    same=[r for r in winner_rows if classify_category(r)==category]
    fallback=False
    selected_category=category
    peers=same
    if not peers:
        ranked=_category_strength(winner_rows)
        if not ranked:
            return {"status":"NO_WINNER_EVIDENCE","requested_category":category,"source_lane":"winners_only","winner_examples":[],"loser_fallback_allowed":False}
        strongest=ranked[0]
        peers=strongest["rows"]; selected_category=strongest["category"]; fallback=True
    examples=[]
    for r in peers:
        p,o,v=r.get("performance") or {},r.get("ocr") or {},r.get("v2_analysis") or {}
        examples.append({"title":p.get("title"),"thumbnail_text":o.get("text"),"ctr":p.get("ctr"),"impressions":p.get("impressions"),"evidence_weight":p.get("evidence_weight"),"visual_analysis":v})
    return {"status":"READY","requested_category":category,"selected_winner_category":selected_category,"fallback_to_strongest_winner_category":fallback,"source_lane":"winners_only","winner_examples":examples,"loser_fallback_allowed":False,"instruction":"Prefer same-category eligible winners. If none exist, use the empirically strongest eligible winner category across the channel. Never use losers as positive priors; keep the new project's supplied title immutable."}

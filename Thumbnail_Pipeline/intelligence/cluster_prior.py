from __future__ import annotations
from statistics import median
from typing import Any
from .settings import load_settings

def _num(v):
    try: return float(v)
    except (TypeError,ValueError): return None

def eligible_cluster_winners(rows:list[dict[str,Any]], settings:dict[str,Any]|None=None)->dict[str,Any]:
    """Select positive priors inside a discovered cluster using configured eligibility + median CTR."""
    cfg=settings or load_settings(); ecfg=cfg.get("eligibility",{})
    floor=ecfg.get("min_impressions"); allowed=set(ecfg.get("allowed_attribution_statuses") or [])
    eligible=[]
    for r in rows:
        p=r.get("performance") or {}; ctr=_num(p.get("ctr")); imp=_num(p.get("impressions"))
        status=str(p.get("attribution_status") or (r.get("attribution") or {}).get("status") or "")
        if ctr is None or imp is None or imp<=0: continue
        if floor is not None and imp<float(floor): continue
        if allowed and status not in allowed: continue
        eligible.append(r)
    minimum=int(cfg.get("winner_loser",{}).get("minimum_category_observations") or 2)
    if len(eligible)<minimum:
        return {"status":"insufficient_cluster_evidence","eligible_count":len(eligible),"winner_rows":[]}
    threshold=median([float((r.get("performance") or {})["ctr"]) for r in eligible])
    winners=[r for r in eligible if float((r.get("performance") or {})["ctr"])>=threshold]
    return {"status":"ready","eligible_count":len(eligible),"threshold_method":"within_discovered_cluster_median_ctr",
            "median_ctr":threshold,"winner_rows":winners}

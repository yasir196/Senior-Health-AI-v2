from __future__ import annotations
from collections import defaultdict
from statistics import median
from typing import Any

def _views(row:dict[str,Any])->float|None:
    try:return float(row.get("views"))
    except (TypeError,ValueError):return None

def annotate_outliers(rows:list[dict[str,Any]],*,minimum_comparison_videos:int=5)->list[dict[str,Any]]:
    """Evidence-based outlier annotation within the same discovery scope.

    Uses a robust median baseline. No video is called an outlier when the
    comparison set is too small or its views are unavailable.
    """
    groups=defaultdict(list)
    for r in rows: groups[str(r.get("search_scope") or "unknown")].append(r)
    out=[]
    for scope,items in groups.items():
        valid=[(r,_views(r)) for r in items if _views(r) is not None]
        baseline=median([v for _,v in valid]) if len(valid)>=minimum_comparison_videos else None
        for r in items:
            x=dict(r); v=_views(r)
            if baseline is None or baseline<=0 or v is None:
                x["outlier_status"]="not_claimed"
                x["outlier_evidence"]={"comparison_scope":scope,"comparison_videos":len(valid),"reason":"insufficient_comparative_evidence"}
            else:
                multiple=v/baseline
                # Do not impose an arbitrary outlier cutoff here. Preserve the
                # comparative strength for downstream ranking/human review.
                x["outlier_status"]="comparative_evidence_available"
                x["outlier_evidence"]={"comparison_scope":scope,"comparison_videos":len(valid),"median_views":baseline,"video_views":v,"views_vs_median_multiple":round(multiple,4)}
            out.append(x)
    return out

def rank_references(rows:list[dict[str,Any]])->list[dict[str,Any]]:
    """Rank references by relevance scope then observed comparative strength."""
    def key(r):
        ev=r.get("outlier_evidence") or {}
        mult=ev.get("views_vs_median_multiple")
        try:m=float(mult)
        except (TypeError,ValueError):m=0.0
        scope=1 if r.get("search_scope")=="same_topic" else 0
        return (scope,m,_views(r) or 0.0)
    return sorted(rows,key=key,reverse=True)

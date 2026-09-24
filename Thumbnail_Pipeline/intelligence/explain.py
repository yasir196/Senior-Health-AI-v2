from __future__ import annotations
from typing import Any
from .settings import load_settings

def explain_group_difference(higher:dict[str,Any],lower:dict[str,Any],min_relative_gap:float|None=None)->list[dict[str,Any]]:
    cfg=load_settings()
    gap=float(cfg.get("explanation",{}).get("minimum_relative_gap",0.0)) if min_relative_gap is None else float(min_relative_gap)
    hi=higher.get("feature_medians",{}); lo=lower.get("feature_medians",{}); findings=[]
    for feature in sorted(set(hi)&set(lo)):
        a,b=hi[feature],lo[feature]
        if not isinstance(a,(int,float)) or not isinstance(b,(int,float)): continue
        scale=max(abs(a),abs(b),1e-9); relative_gap=abs(a-b)/scale
        if relative_gap<gap: continue
        findings.append({"feature":feature,"higher_ctr_median":a,"lower_ctr_median":b,"direction_in_higher_ctr_group":"higher" if a>b else "lower","relative_gap":round(relative_gap,4),"interpretation":"observed_difference_only","claim_strength":"association_only"})
    return sorted(findings,key=lambda x:x["relative_gap"],reverse=True)

def build_why_report(patterns:dict[str,Any])->dict[str,Any]:
    categories={}
    for name,category in patterns.get("category_patterns",{}).items():
        high=category.get("higher_ctr_group"); low=category.get("lower_ctr_group")
        if not high or not low: continue
        categories[name]={"median_ctr":category["median_ctr"],"higher_ctr_observations":high["observations"],"lower_ctr_observations":low["observations"],"observed_feature_differences":explain_group_difference(high,low)}
    return {"method":"Observed winner/loser feature differences within category; no predefined good/bad feature direction.","important":"Associations only, not causal proof.","categories":categories}

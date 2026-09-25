from __future__ import annotations
import math
from collections import defaultdict
from statistics import median
from typing import Any
from .settings import load_settings

NUMERIC_FEATURES=("brightness_mean","contrast_std","edge_density","dark_pixel_ratio","face_count","face_area_ratio","saliency_concentration","clutter_score","tiny_readability_edge_retention","ocr_word_count","ocr_line_count")

def _number(value: Any)->float|None:
    try:
        n=float(value); return n if math.isfinite(n) else None
    except (TypeError,ValueError): return None

def classify_category(row_or_title: Any, settings: dict[str,Any]|None=None)->str:
    cfg=settings or load_settings()
    if isinstance(row_or_title,dict):
        v2=row_or_title.get("v2_analysis") or {}
        value=str(v2.get("hero_category") or "").strip()
        if value: return value
    return str(cfg.get("categorization",{}).get("fallback") or "uncategorized")

def reliability_weight(row: dict[str,Any], settings: dict[str,Any]|None=None)->float:
    cfg=settings or load_settings()
    perf=row.get("performance") or {}
    if cfg.get("eligibility",{}).get("use_v2_evidence_weight",True):
        w=_number(perf.get("evidence_weight"))
        if w is not None: return max(0.0,min(1.0,w))
    imp=_number(perf.get("impressions")) or 0.0
    rcfg=cfg.get("reliability",{})
    floor=float(rcfg.get("impression_floor") or 0.0)
    full=float(rcfg.get("full_reliability_impressions") or 0.0)
    if full<=floor: return 1.0 if imp>=floor and floor>0 else 0.0
    if imp<=floor: return 0.0
    if imp>=full: return 1.0
    return round((imp-floor)/(full-floor),6)

def _flatten(row:dict[str,Any])->dict[str,Any]:
    features=dict(row.get("features") or {})
    ocr=dict(row.get("ocr") or {}); perf=dict(row.get("performance") or {})
    return {**features,"ocr_word_count":ocr.get("word_count"),"ocr_line_count":ocr.get("line_count"),"ctr":perf.get("ctr"),"impressions":perf.get("impressions"),"title":perf.get("title")}

def _summary(rows:list[dict[str,Any]])->dict[str,Any]:
    result={"observations":len(rows)}
    ctrs=[_number(r.get("ctr")) for r in rows]; ctrs=[v for v in ctrs if v is not None]
    result["median_ctr"]=round(median(ctrs),4) if ctrs else None
    fm={}
    for name in NUMERIC_FEATURES:
        vals=[_number(r.get(name)) for r in rows]; vals=[v for v in vals if v is not None]
        if vals: fm[name]=round(median(vals),6)
    result["feature_medians"]=fm; return result

def build_patterns(joined_rows:list[dict[str,Any]],settings:dict[str,Any]|None=None)->dict[str,Any]:
    cfg=settings or load_settings(); ecfg=cfg.get("eligibility",{})
    min_imp=ecfg.get("min_impressions"); allowed=set(ecfg.get("allowed_attribution_statuses") or [])
    eligible_original=[]; excluded=0
    for row in joined_rows:
        perf=row.get("performance") or {}; ctr=_number(perf.get("ctr")); imp=_number(perf.get("impressions"))
        status=str(perf.get("attribution_status") or (row.get("attribution") or {}).get("status") or "")
        if ctr is None or imp is None or imp<=0 or (min_imp is not None and imp<float(min_imp)) or (allowed and status not in allowed):
            excluded+=1; continue
        eligible_original.append(row)
    by_category=defaultdict(list)
    for original in eligible_original:
        row=_flatten(original); row["category"]=classify_category(original,cfg)
        row["reliability_weight"]=reliability_weight(original,settings=cfg); by_category[row["category"]].append(row)
    categories={}; winners=[]; losers=[]
    minimum=int(cfg.get("winner_loser",{}).get("minimum_category_observations") or 2)
    for category,rows in sorted(by_category.items()):
        if len(rows)<minimum:
            categories[category]={"status":"insufficient_observations","all":_summary(rows)}; continue
        threshold=median([r["ctr"] for r in rows]); high=[r for r in rows if r["ctr"]>=threshold]; low=[r for r in rows if r["ctr"]<threshold]
        categories[category]={"status":"comparable","threshold_method":cfg["winner_loser"]["method"],"median_ctr":round(threshold,4),"all":_summary(rows),"higher_ctr_group":_summary(high),"lower_ctr_group":_summary(low)}
        winners+=high; losers+=low
    return {"schema_version":"0.2.0","method":{"eligibility":ecfg,"categorization":cfg.get("categorization"),"winner_loser":cfg.get("winner_loser"),"causality_warning":"Associations only. Do not interpret feature differences as causal CTR effects.","attribution_policy":"Use V2 attribution-aware evidence; do not assign lifetime CTR to arbitrary thumbnail snapshots."},"eligible_observations":len(eligible_original),"excluded_observations":excluded,"winner_patterns":_summary(winners),"loser_patterns":_summary(losers),"category_patterns":categories}

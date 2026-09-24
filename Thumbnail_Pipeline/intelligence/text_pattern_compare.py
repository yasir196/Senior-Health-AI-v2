from __future__ import annotations
from collections import defaultdict
from typing import Any
from .text_psychology import discover_text_patterns
from .settings import load_settings
from .patterns import classify_category

def compare_text_patterns(rows:list[dict[str,Any]],min_impressions:int|None=None,settings:dict[str,Any]|None=None)->dict[str,Any]:
    cfg=settings or load_settings(); floor=cfg["eligibility"]["min_impressions"] if min_impressions is None else min_impressions
    eligible=[]
    for row in rows:
        try:
            if float((row.get("performance") or {}).get("impressions"))>=float(floor): eligible.append(row)
        except (TypeError,ValueError): pass
    discovered=discover_text_patterns(eligible,settings=cfg)
    grouped=defaultdict(list)
    for p in discovered["patterns"]: grouped[p["category"]].append(p)
    return {"method":"within-category channel-discovered text patterns; no seeded psychology vocabulary","categories":dict(grouped)}

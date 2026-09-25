from __future__ import annotations
import re
from collections import Counter, defaultdict
from typing import Any

def _tokens(text: str | None) -> list[str]:
    return re.findall(r"[a-z0-9+'-]+|[?!.]", (text or "").lower())

def _ngrams(tokens: list[str], n: int) -> list[str]:
    words=[t for t in tokens if t not in {"?","!","."}]
    return [" ".join(words[i:i+n]) for i in range(max(0,len(words)-n+1))]

def discover_text_patterns(rows: list[dict[str,Any]], min_observations: int|None=None, settings:dict[str,Any]|None=None) -> dict[str,Any]:
    from .settings import load_settings
    cfg=settings or load_settings()
    if min_observations is None:
        min_observations=int(cfg["text_taxonomy"]["discovery"]["minimum_pattern_observations"])
    """Discover recurring text mechanisms from channel evidence; no seeded psychology labels/cues."""
    groups=defaultdict(list)
    for row in rows:
        perf=row.get("performance") or {}; ocr=row.get("ocr") or {}; v2=row.get("v2_analysis") or {}
        text=str(ocr.get("text") or "").strip()
        if not text: continue
        try: ctr=float(perf.get("ctr")); imp=float(perf.get("impressions"))
        except (TypeError,ValueError): continue
        if imp<=0: continue
        category=str(v2.get("hero_category") or "uncategorized")
        tokens=_tokens(text)
        mechanisms=set()
        for n in (1,2,3):
            mechanisms.update(_ngrams(tokens,n))
        if "?" in text: mechanisms.add("<question_mark>")
        if "!" in text: mechanisms.add("<exclamation_mark>")
        mechanisms.add(f"<word_count:{len([t for t in tokens if t not in {'?','!','.'}])}>")
        for mechanism in mechanisms:
            groups[(category,mechanism)].append({"ctr":ctr,"impressions":imp,"title":perf.get("title"),"thumbnail_text_full":text})

    discovered=[]
    for (category,mechanism),examples in groups.items():
        if len(examples)<min_observations: continue
        total=sum(x["impressions"] for x in examples)
        weighted=(sum(x["ctr"]*x["impressions"] for x in examples)/total) if total else None
        discovered.append({
            "discovered_pattern":mechanism,
            "category":category,
            "observations":len(examples),
            "total_impressions":total,
            "impression_weighted_ctr":round(weighted,4) if weighted is not None else None,
            "examples":examples,
            "label_source":"channel_data_discovery",
            "human_review_status":"unreviewed",
        })
    discovered.sort(key=lambda x:(x["category"],-x["observations"],-x["total_impressions"],x["discovered_pattern"]))
    return {"method":"channel_data_discovery_no_seeded_psychology_vocabulary","patterns":discovered}

def pattern_word_map(text: str | None, discovered_patterns: list[dict[str,Any]] | None=None) -> list[dict[str,Any]]:
    """Ordered audit map; preserves duplicate token occurrences. Labels come only from discovered channel patterns."""
    raw=text or ""; tokens=re.findall(r"[A-Za-z0-9+'-]+|[?!.]",raw)
    patterns=[str(x.get("discovered_pattern") or "") for x in (discovered_patterns or [])]
    out=[]
    for i,token in enumerate(tokens):
        low=token.lower()
        matches=[p for p in patterns if p==low or (not p.startswith("<") and low in p.split())]
        out.append({"index":i,"token":token,"discovered_patterns":matches,"status":"matched" if matches else "unclassified"})
    return out

def summarize_psychology(rows:list[dict[str,Any]],settings:dict[str,Any]|None=None)->dict[str,Any]:
    discovered=discover_text_patterns(rows,settings=settings)
    by_category=defaultdict(list)
    for p in discovered["patterns"]: by_category[p["category"]].append(p)
    examples=[]
    all_patterns=discovered["patterns"]
    for row in rows:
        perf=row.get("performance") or {}; ocr=row.get("ocr") or {}; v2=row.get("v2_analysis") or {}
        text=str(ocr.get("text") or "")
        category=str(v2.get("hero_category") or "uncategorized")
        relevant=by_category.get(category,[])
        examples.append({
            "title":perf.get("title"),"thumbnail_text_full":text,"category":category,
            "full_word_pattern_map":pattern_word_map(text,relevant),
            "ctr":perf.get("ctr"),"impressions":perf.get("impressions")
        })
    return {**discovered,"examples":examples}

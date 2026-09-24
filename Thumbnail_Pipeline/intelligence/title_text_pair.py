from __future__ import annotations
import re
from typing import Any

def _tokens(text:str|None)->set[str]:
    return {w for w in re.findall(r"[a-z0-9]+",(text or "").lower()) if len(w)>1}

def pair_features(title:str|None,thumbnail_text:str|None)->dict[str,Any]:
    title_tokens=_tokens(title); thumb_tokens=_tokens(thumbnail_text)
    overlap=title_tokens & thumb_tokens; union=title_tokens | thumb_tokens
    return {"title_word_count":len((title or "").split()),"thumbnail_word_count":len((thumbnail_text or "").split()),"shared_tokens":sorted(overlap),"token_overlap_ratio":round(len(overlap)/max(1,len(union)),4),"thumbnail_adds_new_tokens":bool(thumb_tokens-title_tokens),"new_thumbnail_tokens":sorted(thumb_tokens-title_tokens)}

def summarize_title_text_pairs(rows:list[dict[str,Any]])->dict[str,Any]:
    pairs=[]
    for row in rows:
        perf=row.get("performance") or {}; ocr=row.get("ocr") or {}
        pairs.append({"title":perf.get("title"),"thumbnail_text":ocr.get("text"),**pair_features(perf.get("title"),ocr.get("text")),"ctr":perf.get("ctr"),"impressions":perf.get("impressions")})
    return {"method":"neutral_title_text_overlap_no_seeded_hook_vocabulary","observations":len(pairs),"pairs":pairs}

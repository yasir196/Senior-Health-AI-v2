from __future__ import annotations
import re
from collections import Counter
from typing import Any

def _tokens(text:str)->list[str]:
    return re.findall(r"[a-z0-9]+",(text or "").lower())

def _lines(text:str)->list[str]:
    return [x.strip() for x in (text or "").splitlines() if x.strip()]

def _subsequence_positions(needle:list[str], haystack:list[str])->list[int]:
    out=[]; start=0
    for token in needle:
        try: pos=haystack.index(token,start)
        except ValueError: return []
        out.append(pos); start=pos+1
    return out

def _template(title:str, overlay:str)->dict[str,Any]:
    tt=_tokens(title); ot=_tokens(overlay); title_set=set(tt)
    skeleton=[]; literals=[]; slots=[]
    for token in ot:
        if token in title_set:
            skeleton.append("<TITLE>")
            slots.append(token)
        else:
            skeleton.append(token)
            literals.append(token)
    return {"skeleton":skeleton,"literal_tokens":literals,"title_tokens":slots,
            "overlay_word_count":len(ot),"overlay_line_count":len(_lines(overlay)),
            "ends_question":overlay.rstrip().endswith("?"),"ends_exclamation":overlay.rstrip().endswith("!"),
            "title_positions":_subsequence_positions(slots,tt)}

def discover_text_mechanisms(rows:list[dict[str,Any]])->dict[str,Any]:
    """Discover title→overlay transformations from eligible cluster winners only."""
    observations=[]
    for r in rows:
        p=r.get("performance") or {}; o=r.get("ocr") or {}
        title=str(p.get("title") or ""); overlay=str(o.get("text") or "").strip()
        if not title or not overlay: continue
        t=_template(title,overlay)
        observations.append({"title":title,"historical_overlay":overlay,**t})
    if not observations: return {"status":"no_text_evidence","observations":[],"patterns":[],"profile":{}}
    keys=Counter(tuple(o["skeleton"]) for o in observations)
    patterns=[]
    for skeleton,count in keys.most_common():
        examples=[o for o in observations if tuple(o["skeleton"])==skeleton]
        patterns.append({"skeleton":list(skeleton),"observations":count,
                         "example_count":len(examples),
                         "question_rate":sum(x["ends_question"] for x in examples)/len(examples),
                         "line_count_mode":Counter(x["overlay_line_count"] for x in examples).most_common(1)[0][0]})
    def mode(key):
        return Counter(o[key] for o in observations).most_common(1)[0][0]
    return {"status":"ready","observations":observations,"patterns":patterns,
            "profile":{"typical_overlay_word_count":mode("overlay_word_count"),
                       "typical_overlay_line_count":mode("overlay_line_count"),
                       "question_form_rate":sum(o["ends_question"] for o in observations)/len(observations)}}

def _instantiate(title:str, pattern:dict[str,Any])->str|None:
    words=re.findall(r"[A-Za-z0-9']+",title or "")
    if not words: return None
    skeleton=pattern.get("skeleton") or []
    slot_count=sum(1 for x in skeleton if x=="<TITLE>")
    if slot_count<=0: return None
    # Slot values are selected from the current immutable title only. Literal transformation
    # tokens are admitted only because they were discovered in eligible historical winners.
    selected=words[:slot_count]
    it=iter(selected); out=[]
    for token in skeleton:
        out.append(next(it) if token=="<TITLE>" else str(token))
    text=" ".join(out).strip()
    if pattern.get("question_rate",0)>=0.5: text=text.rstrip("?!")+"?"
    return text.upper()

def transformation_text_candidates(title:str, mechanism:dict[str,Any], limit:int=5)->list[str]:
    candidates=[]
    for pattern in mechanism.get("patterns") or []:
        text=_instantiate(title,pattern)
        if text and text not in candidates:
            candidates.append(text)
        if len(candidates)>=limit: break
    return candidates

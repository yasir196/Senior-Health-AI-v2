from __future__ import annotations
import re
from collections import Counter
from typing import Any

def _tokens(text:str)->list[str]:
    return re.findall(r"[a-z0-9]+",(text or "").lower())

def discover_text_mechanisms(rows:list[dict[str,Any]])->dict[str,Any]:
    """Describe recurring title/overlay relationships; no seeded hook words or semantic categories."""
    observations=[]
    for r in rows:
        p=r.get("performance") or {}; o=r.get("ocr") or {}
        title=str(p.get("title") or ""); overlay=str(o.get("text") or "").strip()
        if not overlay: continue
        tt=set(_tokens(title)); ot=_tokens(overlay); shared=[x for x in ot if x in tt]
        observations.append({"title":title,"historical_overlay":overlay,"overlay_word_count":len(ot),
            "overlay_line_count":len([x for x in overlay.splitlines() if x.strip()]),
            "shared_title_tokens":shared,"shared_token_count":len(shared),
            "ends_question":overlay.rstrip().endswith("?")})
    if not observations: return {"status":"no_text_evidence","observations":[],"profile":{}}
    def mode(key):
        vals=[o[key] for o in observations]
        return Counter(vals).most_common(1)[0][0] if vals else None
    return {"status":"ready","observations":observations,
            "profile":{"typical_overlay_word_count":mode("overlay_word_count"),
                       "typical_overlay_line_count":mode("overlay_line_count"),
                       "typical_shared_token_count":mode("shared_token_count"),
                       "question_form_rate":sum(1 for o in observations if o["ends_question"])/len(observations)}}

def title_bound_text_candidates(title:str, mechanism:dict[str,Any], limit:int=5)->list[str]:
    """Return only evidence-bound text fragments already present in the immutable title.
    This deliberately refuses to invent hook vocabulary. Historical overlays are never copied.
    """
    profile=mechanism.get("profile") or {}
    target=int(profile.get("typical_overlay_word_count") or 0)
    words=re.findall(r"[A-Za-z0-9']+",title or "")
    if not words or target<=0: return []
    target=max(1,min(target,len(words)))
    candidates=[]
    # Data controls length; title controls vocabulary. Produce distinct contiguous windows only.
    for start in range(0,max(1,len(words)-target+1)):
        text=" ".join(words[start:start+target]).upper()
        if text and text not in candidates: candidates.append(text)
        if len(candidates)>=limit: break
    return candidates

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

def _candidate_score(text:str, title:str, mechanism:dict[str,Any])->tuple[float,dict[str,Any]]:
    words=_tokens(text); title_words=set(_tokens(title))
    if not words: return (-1.0,{"valid":False,"reason":"empty"})
    observed_literals={str(x) for p in (mechanism.get("patterns") or []) for x in (p.get("skeleton") or []) if x!="<TITLE>"}
    unsupported=[w for w in words if w not in title_words and w not in observed_literals]
    if unsupported: return (-1.0,{"valid":False,"reason":"unsupported_vocabulary","tokens":unsupported})
    profile=mechanism.get("profile") or {}
    target=float(profile.get("typical_overlay_word_count") or len(words))
    length_fit=1.0-(abs(len(words)-target)/max(1.0,target))
    title_overlap=sum(1 for w in words if w in title_words)/len(words)
    duplicate_penalty=(len(words)-len(set(words)))/len(words)
    # Reject transformations that are not recurrent across eligible winners. A one-off
    # historical overlay is evidence, but not a reusable transformation rule.
    matching=[p for p in (mechanism.get("patterns") or []) if all(str(x) in words or str(x)=="<TITLE>" for x in (p.get("skeleton") or []))]
    recurrence=max([int(p.get("observations") or 0) for p in matching] or [0])
    if recurrence < 2:
        return (-1.0,{"valid":False,"reason":"insufficient_pattern_recurrence","observations":recurrence})
    # Structural sanity comes from the observed profile, not a hook-word blacklist.
    if length_fit < 0:
        return (-1.0,{"valid":False,"reason":"length_outside_observed_profile","length_fit":round(length_fit,4)})
    score=length_fit+title_overlap-duplicate_penalty
    return (score,{"valid":True,"length_fit":round(length_fit,4),"title_overlap":round(title_overlap,4),"duplicate_penalty":round(duplicate_penalty,4),"pattern_observations":recurrence})

def transformation_text_candidates(title:str, mechanism:dict[str,Any], limit:int=5, with_audit:bool=False):
    ranked=[]
    for pattern in mechanism.get("patterns") or []:
        text=_instantiate(title,pattern)
        if not text: continue
        score,audit=_candidate_score(text,title,mechanism)
        if audit.get("valid"):
            ranked.append({"text":text,"score":round(score,4),"audit":audit})
    ranked.sort(key=lambda x:(x["score"],x["text"]),reverse=True)
    unique=[]; seen=set()
    for item in ranked:
        if item["text"] in seen: continue
        seen.add(item["text"]); unique.append(item)
        if len(unique)>=limit: break
    return unique if with_audit else [x["text"] for x in unique]


def _observed_title_token_frequency(mechanism:dict[str,Any])->Counter:
    freq=Counter()
    for o in mechanism.get("observations") or []:
        freq.update(set(_tokens(str(o.get("title") or ""))))
    return freq

def _current_title_subject_tokens(title:str, mechanism:dict[str,Any], limit:int=2)->list[str]:
    """Choose current-title anchor tokens by corpus distinctiveness, not a seeded subject vocabulary."""
    raw=re.findall(r"[A-Za-z0-9']+",title or "")
    if not raw: return []
    freq=_observed_title_token_frequency(mechanism)
    indexed=[]
    for i,w in enumerate(raw):
        t=w.lower().strip("'")
        if not t: continue
        # Prefer tokens rare in historical winner titles; ties preserve current-title order.
        indexed.append((freq.get(t,0),i,w))
    indexed.sort(key=lambda x:(x[0],x[1]))
    chosen=sorted(indexed[:max(1,limit)],key=lambda x:x[1])
    return [x[2] for x in chosen]

def constraint_text_candidates(title:str, mechanism:dict[str,Any], limit:int=5, with_audit:bool=False):
    """Fallback composer: learn structural constraints, then use only current-title words.

    It intentionally adds no fixed hook vocabulary. When recurrent literal transformations
    are unavailable, candidates are concise current-title anchors shaped by observed winner
    word-count/question-form constraints.
    """
    if mechanism.get("status")!="ready": return []
    profile=mechanism.get("profile") or {}
    target=max(1,int(profile.get("typical_overlay_word_count") or 1))
    anchors=_current_title_subject_tokens(title,mechanism,limit=min(2,target))
    if not anchors: return []
    title_words=re.findall(r"[A-Za-z0-9']+",title or "")
    candidates=[]
    # Anchor-only candidate.
    candidates.append(" ".join(anchors))
    # Evidence-sized current-title phrase around the strongest anchor, without invented words.
    anchor=anchors[0].lower()
    lower=[w.lower().strip("'") for w in title_words]
    try: center=lower.index(anchor)
    except ValueError: center=0
    width=min(target,len(title_words))
    start=max(0,min(center-width//2,len(title_words)-width))
    phrase=" ".join(title_words[start:start+width])
    if phrase and phrase.lower()!=" ".join(anchors).lower(): candidates.append(phrase)
    question_rate=float(profile.get("question_form_rate") or 0)
    out=[]
    for text in candidates:
        rendered=text.upper()
        if question_rate>=0.5: rendered=rendered.rstrip("?!")+"?"
        audit={"valid":True,"source":"constraint_fallback","uses_current_title_words_only":True,
               "target_word_count":target,"question_form_rate":round(question_rate,4)}
        item={"text":rendered,"score":1.0 if len(_tokens(rendered))==target else 0.5,"audit":audit}
        if rendered not in [x["text"] for x in out]: out.append(item)
        if len(out)>=limit: break
    return out if with_audit else [x["text"] for x in out]

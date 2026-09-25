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
    # A discovered external pattern can contain more title-derived slots than the
    # current immutable title has tokens. Such a pattern is not instantiable here;
    # reject it rather than crashing or fabricating/repeating title words.
    if slot_count > len(words):
        return None
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


def recurrent_observed_text_candidates(title:str, mechanism:dict[str,Any], limit:int=5, with_audit:bool=False):
    """Reuse recurrent observed overlays when they are already supported by the current title.

    This lane is intentionally conservative: it never substitutes positional title slots.
    Every lexical word in the observed overlay must occur in the immutable current title;
    punctuation/symbols may be preserved. Thus evidence such as CLOVE + COFFEE? can survive
    unchanged, while ONE CLOVE DAILY is not rewritten into ONE 1 DAILY.
    """
    title_words=set(_tokens(title))
    counts=Counter()
    originals={}
    for obs in mechanism.get("observations") or []:
        raw=str(obs.get("historical_overlay") or "").strip()
        if not raw:
            continue
        key=" ".join(_tokens(raw))
        if not key:
            continue
        counts[key]+=1
        originals.setdefault(key,raw)
    ranked=[]
    for key,count in counts.items():
        if count < 2:
            continue
        raw=originals[key]
        words=_tokens(raw)
        if not words or any(w not in title_words for w in words):
            continue
        rendered=raw.upper()
        ranked.append({"text":rendered,"score":float(count),
                       "audit":{"valid":True,"source":"recurrent_observed_overlay",
                                "observations":count,"unchanged_observed_text":True,
                                "all_words_supported_by_current_title":True}})
    ranked.sort(key=lambda x:(x["score"],len(_tokens(x["text"]))),reverse=True)
    out=[]; seen=set()
    for item in ranked:
        if item["text"] in seen:
            continue
        seen.add(item["text"]); out.append(item)
        if len(out)>=limit:
            break
    return out if with_audit else [x["text"] for x in out]

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

def _title_roles(title:str, mechanism:dict[str,Any])->dict[str,Any]:
    """Infer subject/context/promise spans from corpus novelty and title structure.

    No topic or hook vocabulary is seeded here. The least-observed lexical token is the
    subject anchor; surrounding contiguous spans provide context; a parenthetical or
    trailing clause is retained as a promise candidate.
    """
    words=re.findall(r"[A-Za-z0-9']+",title or "")
    lexical=[(i,w,w.lower().strip("'")) for i,w in enumerate(words)
             if w.lower().strip("'") and not w.lower().strip("'").isdigit()]
    if not lexical:
        return {"subject":None,"context":[],"promise":None}
    freq=_observed_title_token_frequency(mechanism)
    subject=min(lexical,key=lambda x:(freq.get(x[2],0),x[0]))
    si=subject[0]
    contexts=[]
    # Subject context is cumulative: for each direction retain only the most complete
    # subject-bearing span. Shorter prefixes are intermediate fragments, not final copy.
    containing=[]
    for width in (3,4):
        for start in range(max(0,si-width+1),min(si+1,len(words)-width+1)):
            phrase=" ".join(words[start:start+width])
            if phrase and phrase.lower()!=subject[1].lower():
                containing.append({"text":phrase,"start":start,"word_count":width,
                                   "end":start+width-1,
                                   "subject_offset":si-start})
    if containing:
        max_width=max(x["word_count"] for x in containing)
        complete=[x for x in containing if x["word_count"]==max_width]
        # Prefer spans where the subject appears near an edge: these preserve a complete
        # following/preceding context instead of clipping both sides around the anchor.
        # A leading numeric modifier belongs with the subject. Prefer the complete span
        # that keeps that modifier when available; otherwise prefer an edge-anchored span.
        numeric_prefix = si > 0 and words[si-1].isdigit()
        if numeric_prefix:
            # Keep the numeric modifier only when the span can also carry the full
            # evidence-sized subject context. If the width cap makes that impossible,
            # prefer the complete lexical context rather than a clipped "1 SUBJECT IN YOUR".
            with_modifier=[x for x in complete if x["start"] <= si-1 <= x["end"]]
            after_subject=[x for x in complete if x["start"]==si]
            contexts=(after_subject or with_modifier or complete)[:1]
        else:
            complete.sort(key=lambda x:(min(x["subject_offset"],x["word_count"]-1-x["subject_offset"]),x["start"]))
            contexts=complete[:1]
    promise=None
    m=re.search(r"\(([^()]+)\)\s*$",title or "")
    if m:
        promise=m.group(1).strip()
    elif len(words)>=3:
        # Trailing clause is only a candidate; scoring below decides whether to use it.
        promise=" ".join(words[-3:])
    return {"subject":subject[1],"subject_index":si,"context":contexts,"promise":promise}

def _current_title_spans(title:str, mechanism:dict[str,Any], max_words:int=4)->list[dict[str,Any]]:
    """Rank coherent contiguous title spans using only historical corpus distinctiveness."""
    raw=re.findall(r"[A-Za-z0-9']+",title or "")
    freq=_observed_title_token_frequency(mechanism)
    lexical=[(i,w,w.lower().strip("'")) for i,w in enumerate(raw) if w.lower().strip("'") and not w.lower().strip("'").isdigit()]
    spans=[]
    for a in range(len(lexical)):
        for b in range(a,min(len(lexical),a+max_words)):
            idxs=[lexical[k][0] for k in range(a,b+1)]
            if idxs != list(range(idxs[0],idxs[-1]+1)): break
            words=[lexical[k][1] for k in range(a,b+1)]
            toks=[lexical[k][2] for k in range(a,b+1)]
            rarity=sum(1.0/(1.0+freq.get(t,0)) for t in toks)/len(toks)
            spans.append({"text":" ".join(words),"start":idxs[0],"word_count":len(words),"rarity":rarity})
    # Rank complete evidence-sized spans ahead of shorter fragments. Rarity is a
    # tie-breaker, not a reason to truncate a phrase.
    spans.sort(key=lambda x:(-x["word_count"],-x["rarity"],x["start"]))
    return spans

def constraint_text_candidates(title:str, mechanism:dict[str,Any], limit:int=5, with_audit:bool=False):
    """Fallback composer: learn structural constraints, then use only current-title words.

    It intentionally adds no fixed hook vocabulary. When recurrent literal transformations
    are unavailable, candidates are concise current-title anchors shaped by observed winner
    word-count/question-form constraints.
    """
    if mechanism.get("status")!="ready": return []
    profile=mechanism.get("profile") or {}
    target=max(1,int(profile.get("typical_overlay_word_count") or 1))
    # A fallback copied only from the current title needs enough context to stand alone.
    # Learn the normal overlay size, but do not let a very short historical overlay force
    # an incomplete title fragment.
    fallback_width=min(4,max(3,target))
    roles=_title_roles(title,mechanism)
    spans=_current_title_spans(title,mechanism,max_words=fallback_width)
    if not spans: return []
    candidates=[]
    # Role-aware ordering: subject-bearing context first, then the title's explicit
    # promise clause, then generic evidence-sized spans. This avoids sliding-window output.
    role_contexts=roles.get("context") or []
    for x in role_contexts:
        candidates.append(x["text"])
    if roles.get("promise"):
        candidates.append(str(roles["promise"]))
    # Generic spans are fallback-only. Once a subject role has a complete context, do not
    # reintroduce shorter sliding-window fragments into the final candidate list.
    if not role_contexts:
        exact=[s for s in spans if s["word_count"]==fallback_width]
        candidates.extend(s["text"] for s in exact)
    if roles.get("subject") and not role_contexts:
        candidates.append(str(roles["subject"]))
    question_rate=float(profile.get("question_form_rate") or 0)
    out=[]
    for text in candidates:
        rendered=text.upper()
        if question_rate>=0.5: rendered=rendered.rstrip("?!")+"?"
        audit={"valid":True,"source":"constraint_fallback","uses_current_title_words_only":True,
               "target_word_count":target,"fallback_span_width":fallback_width,"semantic_roles":roles,"question_form_rate":round(question_rate,4)}
        item={"text":rendered,"score":1.0 if len(_tokens(rendered))==target else 0.5,"audit":audit}
        if rendered not in [x["text"] for x in out]: out.append(item)
        if len(out)>=limit: break
    return out if with_audit else [x["text"] for x in out]

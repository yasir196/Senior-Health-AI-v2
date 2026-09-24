from __future__ import annotations

import re
from collections import Counter
from typing import Any

STOP = {"the","a","an","and","or","of","to","in","for","after","before","is","are","you","your","this","that","what","when","why","how"}


def _tokens(text: str | None) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in STOP and len(w) > 1}


def pair_features(title: str | None, thumbnail_text: str | None) -> dict[str, Any]:
    title_tokens = _tokens(title)
    thumb_tokens = _tokens(thumbnail_text)
    overlap = title_tokens & thumb_tokens
    union = title_tokens | thumb_tokens
    return {
        "title_word_count": len((title or "").split()),
        "thumbnail_word_count": len((thumbnail_text or "").split()),
        "shared_keywords": sorted(overlap),
        "keyword_overlap_ratio": round(len(overlap) / max(1, len(union)), 4),
        "thumbnail_adds_new_information": bool(thumb_tokens - title_tokens),
        "new_thumbnail_keywords": sorted(thumb_tokens - title_tokens),
    }


def hook_type(text: str | None) -> str:
    t = (text or "").strip().lower()
    if not t:
        return "no_text"
    if "?" in t or t.startswith(("what ","why ","where ","how ","which ")):
        return "question"
    if any(x in t for x in ("don't","dont","stop","avoid","never")):
        return "warning_action"
    if any(x in t for x in ("first","start","do this","try this")):
        return "action"
    if any(x in t for x in ("clue","hidden","missed","next","inside")):
        return "curiosity_gap"
    return "statement"


def summarize_title_text_pairs(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = []
    hooks = Counter()
    for row in rows:
        perf = row.get("performance") or {}
        ocr = row.get("ocr") or {}
        title = perf.get("title")
        text = ocr.get("text")
        p = pair_features(title, text)
        hook = hook_type(text)
        hooks[hook] += 1
        pairs.append({
            "title": title,
            "thumbnail_text": text,
            "hook_type": hook,
            **p,
            "ctr": perf.get("ctr"),
            "impressions": perf.get("impressions"),
        })
    return {"observations": len(pairs), "hook_type_counts": dict(hooks), "pairs": pairs}

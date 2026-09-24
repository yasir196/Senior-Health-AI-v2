from __future__ import annotations

import re
from collections import Counter
from typing import Any

PATTERNS = {
    "problem": ("pain","swollen","swelling","hard","dry","weak","difficult","can't","cannot","stuck"),
    "action": ("do","try","start","check","eat","move","use","reheat"),
    "command": ("do this","try this","start here","check this","stop","don't","avoid","never"),
    "question": ("what","why","where","how","which","?"),
    "curiosity": ("hidden","clue","next","inside","really","actually","missed"),
    "contrast": ("but","not","isn't","aren't","instead","vs"),
    "specificity": ("first","one","both","before","after","night","morning"),
    "warning": ("warning","danger","avoid","don't","never","stop"),
    "identity_context": ("after 60","over 60","60+","at night"),
}
STOPWORDS = {"the","a","an","and","or","to","of","in","on","for","is","are","be","your","you","this","that"}


def matched_cues(text: str | None) -> dict[str, list[str]]:
    t = (text or "").lower()
    return {name: [cue for cue in cues if cue in t] for name, cues in PATTERNS.items() if any(cue in t for cue in cues)}


def pattern_word_map(text: str | None) -> dict[str, list[str]]:
    """Map every full OCR token/phrase to the detected pattern(s); preserve source wording."""
    raw = (text or "").strip()
    tokens = re.findall(r"[A-Za-z0-9+'-]+|[?!.]", raw)
    result: dict[str, list[str]] = {}
    lowered = raw.lower()
    for token in tokens:
        token_lower = token.lower()
        labels = []
        for name, cues in PATTERNS.items():
            for cue in cues:
                if cue == "?" and token == "?":
                    labels.append(name)
                elif " " not in cue and cue == token_lower:
                    labels.append(name)
                elif " " in cue and cue in lowered and token_lower in cue.split():
                    labels.append(name)
        result[token] = list(dict.fromkeys(labels)) or ["unclassified"]
    return result


def thumbnail_keywords(text: str | None) -> list[str]:
    words = re.findall(r"[a-z0-9+'-]+", (text or "").lower())
    return list(dict.fromkeys(w for w in words if w not in STOPWORDS and len(w) > 1))


def psychology_tags(text: str | None) -> list[str]:
    tags = list(matched_cues(text))
    return tags or ["neutral_statement"]


def pattern_sequence(text: str | None) -> str:
    tags = psychology_tags(text)
    priority = ("problem","identity_context","contrast","curiosity","question","specificity","action","command","warning")
    ordered = [x for x in priority if x in tags]
    return "".join(f"[{x.upper()}]" for x in ordered) or "[NEUTRAL_STATEMENT]"


def text_shape(text: str | None) -> dict[str, Any]:
    raw = text or ""
    words = re.findall(r"[A-Za-z0-9+'-]+", raw)
    return {
        "word_count": len(words),
        "question_mark": "?" in raw,
        "exclamation_mark": "!" in raw,
        "all_caps_ratio": round(sum(w.isupper() for w in words) / max(1, len(words)), 4),
        "full_thumbnail_text": raw,
        "thumbnail_keywords": thumbnail_keywords(raw),
        "matched_pattern_cues": matched_cues(raw),
        "full_word_pattern_map": pattern_word_map(raw),
        "psychology_tags": psychology_tags(raw),
        "pattern_sequence": pattern_sequence(raw),
    }


def summarize_psychology(rows: list[dict[str, Any]]) -> dict[str, Any]:
    sequences, tags = Counter(), Counter()
    examples: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        perf, ocr = row.get("performance") or {}, row.get("ocr") or {}
        text = ocr.get("text") or ""
        shape = text_shape(text)
        seq = shape["pattern_sequence"]
        sequences[seq] += 1
        tags.update(shape["psychology_tags"])
        examples.setdefault(seq, []).append({
            "title": perf.get("title"),
            "thumbnail_text_full": text,
            "thumbnail_keywords": shape["thumbnail_keywords"],
            "matched_pattern_cues": shape["matched_pattern_cues"],
            "full_word_pattern_map": shape["full_word_pattern_map"],
            "detected_pattern": seq,
            "ctr": perf.get("ctr"),
            "impressions": perf.get("impressions"),
        })
    return {
        "pattern_counts": dict(sequences.most_common()),
        "psychology_counts": dict(tags.most_common()),
        "examples_by_pattern": examples,
    }

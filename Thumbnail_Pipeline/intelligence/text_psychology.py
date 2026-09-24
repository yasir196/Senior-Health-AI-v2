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


def psychology_tags(text: str | None) -> list[str]:
    t = (text or "").lower()
    tags = []
    for name, cues in PATTERNS.items():
        if any(cue in t for cue in cues):
            tags.append(name)
    return tags or ["neutral_statement"]


def pattern_sequence(text: str | None) -> str:
    """Return explicit psychological structure, e.g. [PROBLEM][ACTION][COMMAND]."""
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
        "psychology_tags": psychology_tags(raw),
        "pattern_sequence": pattern_sequence(raw),
    }


def summarize_psychology(rows: list[dict[str, Any]]) -> dict[str, Any]:
    sequences = Counter()
    tags = Counter()
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
            "thumbnail_text": text,
            "ctr": perf.get("ctr"),
            "impressions": perf.get("impressions"),
        })
    return {
        "pattern_counts": dict(sequences.most_common()),
        "psychology_counts": dict(tags.most_common()),
        "examples_by_pattern": examples,
    }

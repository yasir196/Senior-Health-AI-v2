from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


TEXT_FAMILIES = {
    "missing piece",
    "challenge",
    "warning",
    "comparison",
    "question",
    "timing",
    "contradiction",
    "evidence",
    "first step",
}

# These words are too generic to prove that a thumbnail stayed on the title's
# actual subject/promise. They are intentionally conservative; this is only a
# deterministic drift preflight, not a semantic model.
TITLE_STOPWORDS = {
    "a", "an", "and", "are", "after", "at", "before", "best", "can", "do",
    "does", "for", "from", "getting", "good", "help", "how", "in", "is", "it",
    "make", "may", "of", "on", "or", "over", "simple", "that", "the", "these",
    "this", "those", "to", "try", "what", "when", "why", "with", "you", "your",
    "senior", "seniors", "people", "foods", "food", "ways", "things", "tips",
}


@dataclass(frozen=True)
class ThumbnailValidationResult:
    passed: bool
    issues: list[str]
    warnings: list[str]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8-sig")
    except OSError:
        return ""


def _anchor_title(project: Path) -> str:
    try:
        data = json.loads(_read(project / "project.json") or "{}")
    except json.JSONDecodeError:
        return ""
    return str(data.get("anchor_title") or "").strip()


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().lower()


def _distinct_title_terms(title: str) -> list[str]:
    terms = re.findall(r"[a-z0-9]+", title.lower())
    return sorted({t for t in terms if len(t) >= 4 and not t.isdigit() and t not in TITLE_STOPWORDS})


def _concept_numbers(text: str) -> set[int]:
    # Count only actual concept headings, not ranked-table rows or prose mentions.
    nums: set[int] = set()
    for m in re.finditer(r"(?im)^#{2,4}\s+(?:thumbnail\s+)?concept\s*#?\s*(\d+)\b", text):
        nums.add(int(m.group(1)))
    return nums


def _family_mentions(text: str) -> set[str]:
    found: set[str] = set()
    for line in text.splitlines():
        if not re.search(r"(?i)\b(?:text\s+family|thumbnail\s+text\s+family|family)\s*:", line):
            continue
        low = line.lower().replace("-", " ")
        for family in TEXT_FAMILIES:
            if family in low:
                found.add(family)
    return found


def _count_label(text: str, label_pattern: str) -> int:
    return len(re.findall(rf"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?{label_pattern}(?:\*\*)?\s*:", text))


def validate_thumbnail_concepts(project: Path) -> ThumbnailValidationResult:
    """Deterministic post-run structural/consistency gate for Thumbnail_Agent.

    This validator intentionally does not replace medical or creative judgment.
    It rejects missing locks, stale terminology, incomplete option/family coverage,
    missing winner sync, and obvious title-subject drift before the stage is marked
    ready. Semantic quality still belongs to Thumbnail_Agent, but the agent can no
    longer simply omit the required evidence/score/fidelity fields and pass.
    """
    project = Path(project)
    concepts_path = project / "04_thumbnail_concepts.md"
    prompt_path = project / "11_thumbnail_prompt.md"
    concepts = _read(concepts_path)
    prompt = _read(prompt_path)
    issues: list[str] = []
    warnings: list[str] = []

    if not concepts.strip():
        issues.append("04_thumbnail_concepts.md is missing or empty.")
    if not prompt.strip():
        issues.append("11_thumbnail_prompt.md is missing or empty.")
    if issues:
        return ThumbnailValidationResult(False, issues, warnings)

    if not re.search(r"(?im)^##\s+Historical Channel Examples Used\s*$", concepts):
        issues.append("Missing `## Historical Channel Examples Used` section.")

    if "Ranked-table ↔ detailed-winner sync: PASS" not in concepts:
        issues.append("Missing exact `Ranked-table ↔ detailed-winner sync: PASS` verification line.")

    # Internal score terminology must not masquerade as measured YouTube CTR.
    if re.search(r"(?i)\b(?:overall\s+)?CTR\s+Score\s*:", concepts):
        issues.append("Deprecated internal `CTR Score` terminology found; use `Packaging Score` only.")

    concept_nums = _concept_numbers(concepts)
    if len(concept_nums) < 10:
        issues.append(f"Expected 10 detailed thumbnail concepts; found {len(concept_nums)} concept heading(s).")

    for label in ("Text Option A", "Text Option B", "Text Option C"):
        count = _count_label(concepts, re.escape(label))
        if count < 10:
            issues.append(f"{label} is incomplete: found {count}, expected at least 10.")

    packaging_count = _count_label(concepts, r"Packaging\s+Score")
    if packaging_count < 10:
        issues.append(f"Packaging Score coverage is incomplete: found {packaging_count}, expected at least 10.")

    families = _family_mentions(concepts)
    if len(families) < 5:
        issues.append(
            "Fewer than 5 distinct Thumbnail Text Families were explicitly labeled "
            f"({', '.join(sorted(families)) or 'none found'})."
        )

    required_semantic_markers = {
        "Primary-Promise Proximity": r"Primary[- ]Promise Proximity",
        "Whole-Video Promise Coverage": r"Whole[- ]Video Promise Coverage|Promise Coverage",
        "Senior Comprehension": r"Senior Comprehension",
        "Instant Visual Comprehension": r"Instant Visual Comprehension",
    }
    for name, pattern in required_semantic_markers.items():
        if not re.search(pattern, concepts, re.I):
            issues.append(f"Missing required semantic-fit field/check: {name}.")

    if not re.search(r"(?im)^##\s+Text Overlay Specification\s*$", prompt):
        issues.append("11_thumbnail_prompt.md is missing `## Text Overlay Specification`.")

    # Final prompt must explicitly preserve title context. This is not a complete
    # semantic proof, but it catches winner prompts that have drifted to a side topic.
    title = _anchor_title(project)
    if title:
        combined_final = _normalize(prompt)
        distinctive = _distinct_title_terms(title)
        present = [term for term in distinctive if re.search(rf"\b{re.escape(term)}\b", combined_final)]
        if distinctive and not present:
            issues.append(
                "Final thumbnail prompt contains none of the title's distinctive subject/promise terms "
                f"({', '.join(distinctive[:8])}); possible title-promise drift."
            )
        elif len(distinctive) >= 4 and len(present) == 1:
            warnings.append(
                "Final thumbnail prompt contains only one distinctive title term "
                f"(`{present[0]}`); manually confirm whole-video promise fidelity."
            )
    else:
        warnings.append("project.json anchor_title could not be read; title-drift preflight was skipped.")

    return ThumbnailValidationResult(not issues, issues, warnings)

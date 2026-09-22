from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

from production_sheet_contract import canonical_word_count

LEDGER_FILENAME = "06c_scene_ledger.csv"
LEDGER_META_FILENAME = "06c_scene_ledger.meta.json"
LEDGER_SCHEMA = "scene-ledger-v1"

_ABBREVIATIONS = {
    "mr.", "mrs.", "ms.", "dr.", "prof.", "sr.", "jr.", "st.", "vs.", "etc.",
    "e.g.", "i.e.", "u.s.", "u.k.", "a.m.", "p.m.",
}


class SceneSegmentationError(ValueError):
    pass


def normalize_narration(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def extract_narration(markdown: str) -> str:
    """Return spoken narration from the canonical voice-script Markdown container.

    Current Speech Optimizer output is narration-only prose separated by blank lines.
    These exclusions are defensive for legacy/editorial scaffolding and deliberately
    narrow: headings, horizontal rules, fenced blocks, and bracketed Visual Cue lines.
    """
    kept: list[str] = []
    in_fence = False
    for raw in str(markdown or "").splitlines():
        line = raw.strip()
        if line.startswith(chr(96) * 3):
            in_fence = not in_fence
            continue
        if in_fence or not line:
            continue
        if re.match(r"^#{1,6}\s+", line):
            continue
        if re.fullmatch(r"(?:---+|___+|\*\*\*+)", line):
            continue
        if re.match(r"^\[\s*Visual\s+Cue\s*:", line, flags=re.I):
            continue
        kept.append(line)
    return normalize_narration(" ".join(kept))


def narration_digest(markdown: str) -> str:
    narration = normalize_narration(extract_narration(markdown))
    return hashlib.sha256(narration.encode("utf-8")).hexdigest()


def _sentence_spans(text: str) -> list[str]:
    text = normalize_narration(text)
    if not text:
        return []
    spans: list[str] = []
    start = 0
    for match in re.finditer(r'[.!?]+["\')\]]*(?=\s+|$)', text):
        end = match.end()
        candidate = text[start:end].strip()
        last_token = candidate.lower().split()[-1] if candidate.split() else ""
        if last_token in _ABBREVIATIONS:
            continue
        if candidate:
            spans.append(candidate)
        start = end
        while start < len(text) and text[start].isspace():
            start += 1
    tail = text[start:].strip()
    if tail:
        spans.append(tail)
    return spans


def _merge_short_units(units: list[str]) -> list[str]:
    """Merge tiny complete sentences without imposing a hard word ceiling.

    Sentence text remains intact. A short sentence may be grouped with an adjacent
    complete sentence so Production does not create meaningless tiny visual scenes.
    """
    out: list[str] = []
    i = 0
    while i < len(units):
        unit = units[i]
        if canonical_word_count(unit) >= 4:
            out.append(unit)
            i += 1
            continue
        if out:
            out[-1] = normalize_narration(out[-1] + " " + unit)
            i += 1
            continue
        if i + 1 < len(units):
            out.append(normalize_narration(unit + " " + units[i + 1]))
            i += 2
            continue
        out.append(unit)
        i += 1
    return out

def segment_voice_script(text: str) -> list[str]:
    narration = normalize_narration(text)
    if not narration:
        raise SceneSegmentationError("No spoken narration found.")
    units: list[str] = []
    # Sentence boundaries are authoritative for ledger units. The 25-27 word
    # figure is a whole-video pacing target, not a per-sentence hard ceiling.
    # Never split an approved sentence merely to satisfy a word target.
    units = _sentence_spans(narration)
    units = _merge_short_units(units)
    if any(canonical_word_count(x) == 0 for x in units):
        raise SceneSegmentationError("Deterministic ledger produced an invalid unit.")
    if normalize_narration(" ".join(units)) != narration:
        raise SceneSegmentationError("Ledger reconstruction does not match extracted narration.")
    return units


def build_scene_ledger(markdown: str) -> tuple[list[dict[str, str]], dict[str, str]]:
    narration = extract_narration(markdown)
    units = segment_voice_script(narration)
    rows = [{"scene_id": f"S{i:03d}", "script_excerpt": unit} for i, unit in enumerate(units, 1)]
    meta = {
        "schema": LEDGER_SCHEMA,
        "narration_sha256": hashlib.sha256(normalize_narration(narration).encode("utf-8")).hexdigest(),
    }
    return rows, meta


def write_scene_ledger(project: Path, markdown: str) -> None:
    rows, meta = build_scene_ledger(markdown)
    with (project / LEDGER_FILENAME).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["scene_id", "script_excerpt"])
        writer.writeheader()
        writer.writerows(rows)
    (project / LEDGER_META_FILENAME).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def load_scene_ledger(project: Path) -> tuple[list[dict[str, str]], dict[str, str]]:
    ledger_path = project / LEDGER_FILENAME
    meta_path = project / LEDGER_META_FILENAME
    if not ledger_path.is_file() or not meta_path.is_file():
        raise SceneSegmentationError("06c scene ledger and metadata are required.")
    with ledger_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SceneSegmentationError(f"Could not read scene-ledger metadata: {exc}") from exc
    return rows, meta


def validate_ledger_reconstruction(markdown: str, ledger_rows: list[dict[str, str]]) -> list[str]:
    """Prove the persisted ledger still reconstructs the current extracted narration."""
    narration = normalize_narration(extract_narration(markdown))
    units = [normalize_narration(row.get("script_excerpt", "")) for row in ledger_rows]
    if not units or any(not unit for unit in units):
        return ["06c scene ledger is empty or contains an empty narration unit."]
    if normalize_narration(" ".join(units)) != narration:
        return ["06c scene ledger does not reconstruct the current extracted 06a narration exactly."]
    return []


def validate_ledger_freshness(markdown: str, meta: dict[str, str]) -> list[str]:
    expected = str(meta.get("narration_sha256") or "")
    current = narration_digest(markdown)
    if meta.get("schema") != LEDGER_SCHEMA:
        return ["06c scene-ledger metadata schema is missing or unsupported."]
    if not expected or expected != current:
        return ["06c scene ledger is stale: current extracted 06a narration hash does not match ledger metadata."]
    return []


def validate_production_against_ledger(
    production_rows: list[dict[str, str]], ledger_rows: list[dict[str, str]]
) -> list[str]:
    """Require a content/order bijection; scene IDs are deliberately not join keys."""
    issues: list[str] = []
    ledger = [normalize_narration(row.get("script_excerpt", "")) for row in ledger_rows]
    if not ledger or any(not item for item in ledger):
        return ["06c scene ledger is empty or contains an empty narration unit."]
    cursor = 0
    for index, row in enumerate(production_rows, 1):
        excerpt = normalize_narration(row.get("script_excerpt", ""))
        sid = str(row.get("scene_id") or f"row {index}").strip()
        if not excerpt:
            issues.append(f"{sid}: zero-narration Production rows are not permitted.")
            continue
        if cursor >= len(ledger):
            issues.append(f"{sid}: Production row has no remaining ledger narration to consume.")
            continue
        combined = ""
        end = cursor
        matched = False
        while end < len(ledger):
            combined = normalize_narration((combined + " " + ledger[end]).strip())
            if combined == excerpt:
                matched = True
                break
            if len(combined) >= len(excerpt) or not excerpt.startswith(combined + " "):
                break
            end += 1
        if not matched:
            issues.append(f"{sid}: script_excerpt is not one exact consecutive ledger span at source position {cursor + 1}.")
            continue
        cursor = end + 1
    if cursor != len(ledger):
        issues.append(f"Production consumed {cursor} of {len(ledger)} ledger units; every ledger unit must be consumed exactly once.")
    return issues

import json
from pathlib import Path

from thumbnail_concept_validation import validate_thumbnail_concepts


def _valid_concepts() -> str:
    rows = ["# Thumbnail Concepts", "", "## Historical Channel Examples Used", "NO MATCHING HISTORICAL EXAMPLES AVAILABLE", ""]
    families = ["Question", "Warning", "Comparison", "Timing", "Evidence", "Missing Piece"]
    for i in range(1, 11):
        fam = families[(i - 1) % len(families)]
        rows += [
            f"## Concept {i}",
            "Primary-Promise Proximity: PASS",
            "Whole-Video Promise Coverage: 9/10",
            "Senior Comprehension: 9/10",
            "Instant Visual Comprehension: 9/10",
            f"Text Option A: OPTION A {i}",
            f"Thumbnail Text Family: {fam}",
            f"Text Option B: OPTION B {i}",
            f"Text Option C: OPTION C {i}",
            "Recommended Winner: OPTION A",
            "Packaging Score: 90/100",
            "Medical Safety: PASS",
            "",
        ]
    rows += ["Ranked-table ↔ detailed-winner sync: PASS", ""]
    return "\n".join(rows)


def _valid_prompt() -> str:
    return """# Final Thumbnail Prompt

Title context: Bones Getting Weaker After 60? Try These 3 Simple Calcium Rich Foods
Hero visual: clear bone-strength cue beside three calcium-rich foods.

## Text Overlay Specification
Overlay: GETTING ENOUGH?
"""


def test_validator_passes_complete_thumbnail_package(tmp_path: Path):
    (tmp_path / "project.json").write_text(json.dumps({"anchor_title": "Bones Getting Weaker After 60? Try These 3 Simple Calcium Rich Foods"}), encoding="utf-8")
    (tmp_path / "04_thumbnail_concepts.md").write_text(_valid_concepts(), encoding="utf-8")
    (tmp_path / "11_thumbnail_prompt.md").write_text(_valid_prompt(), encoding="utf-8")
    result = validate_thumbnail_concepts(tmp_path)
    assert result.passed, result.issues


def test_validator_rejects_old_ctr_score_and_missing_sync(tmp_path: Path):
    (tmp_path / "project.json").write_text(json.dumps({"anchor_title": "Bones Getting Weaker After 60? Try These 3 Simple Calcium Rich Foods"}), encoding="utf-8")
    bad = _valid_concepts().replace("Packaging Score: 90/100", "CTR Score: 90/100").replace("Ranked-table ↔ detailed-winner sync: PASS", "")
    (tmp_path / "04_thumbnail_concepts.md").write_text(bad, encoding="utf-8")
    (tmp_path / "11_thumbnail_prompt.md").write_text(_valid_prompt(), encoding="utf-8")
    result = validate_thumbnail_concepts(tmp_path)
    assert not result.passed
    assert any("CTR Score" in x for x in result.issues)
    assert any("detailed-winner sync" in x for x in result.issues)


def test_validator_rejects_obvious_title_subject_drift(tmp_path: Path):
    (tmp_path / "project.json").write_text(json.dumps({"anchor_title": "Bones Getting Weaker After 60? Try These 3 Simple Calcium Rich Foods"}), encoding="utf-8")
    (tmp_path / "04_thumbnail_concepts.md").write_text(_valid_concepts(), encoding="utf-8")
    (tmp_path / "11_thumbnail_prompt.md").write_text("# Final Thumbnail Prompt\n\nGrocery label checking mystery with three packages.\n\n## Text Overlay Specification\nCHECK BEFORE PICKING\n", encoding="utf-8")
    result = validate_thumbnail_concepts(tmp_path)
    assert not result.passed
    assert any("title-promise drift" in x.lower() for x in result.issues)


def test_root_agent_has_no_old_thumbnail_conflicts():
    root = Path(__file__).resolve().parents[1]
    text = (root / "AGENT.md").read_text(encoding="utf-8")
    assert "Overall CTR Score" not in text
    assert "text exceeds 4 words" not in text
    assert "Packaging Score" in text
    assert "There is no universal four-word maximum" in text

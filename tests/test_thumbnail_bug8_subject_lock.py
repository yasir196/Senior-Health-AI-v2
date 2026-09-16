import json
from pathlib import Path

from thumbnail_concept_validation import validate_thumbnail_concepts


TITLE = "Bones Getting Weaker After 60? Try These 3 Simple Calcium Rich Foods"


def _concepts() -> str:
    families = ["question", "comparison", "warning", "evidence", "missing piece"]
    blocks = [
        "## Historical Channel Examples Used",
        "Ranked-table ↔ detailed-winner sync: PASS",
        "Primary-Promise Proximity: PASS",
        "Whole-Video Promise Coverage: PASS",
        "Senior Comprehension: PASS",
        "Instant Visual Comprehension: PASS",
    ]
    for i in range(1, 11):
        blocks.extend(
            [
                f"## Concept {i}",
                f"Text Family: {families[(i - 1) % len(families)]}",
                "Text Option A: A",
                "Text Option B: B",
                "Text Option C: C",
                "Packaging Score: 90/100",
            ]
        )
    return "\n".join(blocks)


def _prompt(overlay: str | None, hidden_prompt: str = "calcium-fortified foods") -> str:
    if overlay is None:
        overlay_block = "Font: bold condensed\nColor: white and yellow"
    else:
        overlay_block = f"Final overlay text: {overlay}\nFont: bold condensed\nColor: white and yellow"
    return (
        "# Final Thumbnail Prompt\n"
        f"Final image prompt: {hidden_prompt}.\n\n"
        "## Text Overlay Specification\n"
        f"{overlay_block}\n\n"
        "## Negative Prompt\nNo fake medical claims.\n"
    )


def _project(tmp_path: Path, overlay: str | None, title: str = TITLE, hidden_prompt: str = "calcium-fortified foods") -> Path:
    (tmp_path / "project.json").write_text(json.dumps({"anchor_title": title}), encoding="utf-8")
    (tmp_path / "04_thumbnail_concepts.md").write_text(_concepts(), encoding="utf-8")
    (tmp_path / "11_thumbnail_prompt.md").write_text(_prompt(overlay, hidden_prompt=hidden_prompt), encoding="utf-8")
    return tmp_path


def test_bug8_ambiguous_bone_overlay_fails_even_when_hidden_prompt_mentions_calcium(tmp_path):
    result = validate_thumbnail_concepts(_project(tmp_path, "WHAT MAKES EACH ONE COUNT?"))
    assert not result.passed
    assert any("viewer-facing overlay" in issue and "bone" in issue for issue in result.issues)


def test_bug8_calcium_rich_overlay_passes(tmp_path):
    result = validate_thumbnail_concepts(_project(tmp_path, "WHAT MAKES THESE CALCIUM-RICH?"))
    assert result.passed, result.issues


def test_bug8_bone_health_overlay_passes(tmp_path):
    result = validate_thumbnail_concepts(_project(tmp_path, "BONE-HEALTH FOOD CHECK"))
    assert result.passed, result.issues


def test_bug8_missing_overlay_blocks_known_bone_subject(tmp_path):
    result = validate_thumbnail_concepts(_project(tmp_path, None))
    assert not result.passed
    assert any("viewer-facing overlay" in issue for issue in result.issues)


def test_bug8_unmapped_title_gets_no_new_subject_block(tmp_path):
    title = "The Tea Mistake Many Seniors Make Before Sleep"
    result = validate_thumbnail_concepts(
        _project(
            tmp_path,
            "WHAT'S IN YOUR NIGHT CUP?",
            title=title,
            hidden_prompt="night tea cup before sleep",
        )
    )
    assert result.passed, result.issues

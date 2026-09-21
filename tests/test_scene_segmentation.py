import pytest

from production_sheet_contract import canonical_word_count, _word_count
from scene_segmentation import (
    SceneSegmentationError,
    build_scene_ledger,
    extract_narration,
    normalize_narration,
    segment_voice_script,
    validate_ledger_freshness,
    validate_production_against_ledger,
)


def test_public_word_counter_preserves_canonical_token_semantics():
    text = "well-being don't don’t"
    assert canonical_word_count(text) == 3
    assert _word_count(text) == canonical_word_count(text)


def test_extract_narration_strips_known_nonspoken_markdown_scaffolding():
    markdown = """# Title

# Hook
Spoken first sentence.

[Visual Cue: kitchen table]
Spoken second sentence.

---
"""
    assert extract_narration(markdown) == "Spoken first sentence. Spoken second sentence."


def test_constipation_voice_script_shape_is_narration_only_fixture():
    voice = """If hard, dry stool has become a regular problem after 60, the first answer may not be "just drink more water."

You deserve a clearer next step than guessing at the pharmacy shelf, or quietly suffering with it.

I am Adrian Westbrook, a Health Educator with Evidence After 60."""
    assert extract_narration(voice) == normalize_narration(voice)


def test_repeatability_and_round_trip():
    text = "This is a complete first sentence with enough words to stand on its own. This is another complete sentence that follows it naturally."
    first = segment_voice_script(text)
    assert first == segment_voice_script(text)
    assert normalize_narration(" ".join(first)) == normalize_narration(text)


def test_decimal_does_not_end_sentence():
    text = "The measured value was 18.9 percent in this example, and that decimal stays inside the sentence. This second sentence remains separate."
    units = segment_voice_script(text)
    assert normalize_narration(" ".join(units)) == normalize_narration(text)
    assert not any(unit.endswith("18.") for unit in units)


def test_abbreviation_does_not_end_sentence():
    text = "Dr. Smith reviewed the example carefully with the group before the discussion continued. The next complete sentence follows normally."
    units = segment_voice_script(text)
    assert normalize_narration(" ".join(units)) == normalize_narration(text)
    assert not any(unit == "Dr." for unit in units)


def test_over_28_with_natural_boundary_splits_under_margin():
    text = "One two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen, sixteen seventeen eighteen nineteen twenty twenty-one twenty-two twenty-three twenty-four twenty-five twenty-six twenty-seven twenty-eight twenty-nine thirty thirty-one thirty-two thirty-three."
    units = segment_voice_script(text)
    assert len(units) >= 2
    assert all(canonical_word_count(unit) <= 28 for unit in units)
    assert normalize_narration(" ".join(units)) == normalize_narration(text)


def test_29_to_32_without_boundary_is_preserved():
    text = "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty twenty-one twenty-two twenty-three twenty-four twenty-five twenty-six twenty-seven twenty-eight twenty-nine."
    units = segment_voice_script(text)
    assert units == [text]


def test_unsegmentable_over_32_fails_explicitly():
    text = " ".join(f"word{i}" for i in range(1, 34)) + "."
    with pytest.raises(SceneSegmentationError, match="above the legal 32-word ceiling"):
        segment_voice_script(text)


def test_short_fragment_merges_without_marker_authority():
    text = "Ask first. This longer sentence provides the adjacent narration needed for a deterministic legal merge."
    units = segment_voice_script(text)
    assert all(canonical_word_count(unit) >= 4 for unit in units)
    assert normalize_narration(" ".join(units)) == normalize_narration(text)


def test_stale_ledger_hash_rejects_spoken_change_but_ignores_stripped_heading():
    original = "This spoken sentence is stable and long enough for the ledger."
    _rows, meta = build_scene_ledger(original)
    assert validate_ledger_freshness(original, meta) == []
    assert validate_ledger_freshness("# Internal heading\n\n" + original, meta) == []
    assert validate_ledger_freshness(original + " Another spoken sentence changes the narration.", meta)


def _ledger(*units):
    return [{"scene_id": f"S{i:03d}", "script_excerpt": unit} for i, unit in enumerate(units, 1)]


def _prod(*units):
    return [{"scene_id": f"SC{i:03d}", "script_excerpt": unit, "notes": ""} for i, unit in enumerate(units, 1)]


def test_parallel_walk_accepts_exact_units_without_id_join():
    ledger = _ledger("Alpha narration has enough words here.", "Beta narration has enough words here.")
    prod = _prod("Alpha narration has enough words here.", "Beta narration has enough words here.")
    assert validate_production_against_ledger(prod, ledger) == []


def test_parallel_walk_accepts_consecutive_merge():
    ledger = _ledger("Alpha narration has enough words here.", "Beta narration has enough words here.")
    prod = _prod("Alpha narration has enough words here. Beta narration has enough words here.")
    assert validate_production_against_ledger(prod, ledger) == []


@pytest.mark.parametrize("prod", [
    _prod("Alpha narration has enough words here."),
    _prod("Beta narration has enough words here.", "Alpha narration has enough words here."),
    _prod("Alpha narration has changed words here.", "Beta narration has enough words here."),
])
def test_parallel_walk_rejects_skip_reorder_or_mutation(prod):
    ledger = _ledger("Alpha narration has enough words here.", "Beta narration has enough words here.")
    assert validate_production_against_ledger(prod, ledger)


def test_parallel_walk_rejects_extra_or_empty_production_row():
    ledger = _ledger("Alpha narration has enough words here.")
    assert validate_production_against_ledger(
        _prod("Alpha narration has enough words here.", "Invented narration has no ledger source."), ledger
    )
    assert validate_production_against_ledger(
        _prod("Alpha narration has enough words here.", ""), ledger
    )

import pytest

from production_sheet_contract import canonical_word_count, _word_count
from scene_segmentation import (
    SceneSegmentationError,
    build_scene_ledger,
    extract_narration,
    normalize_narration,
    segment_voice_script,
    validate_ledger_freshness,
    validate_ledger_reconstruction,
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



def test_two_complete_sentences_produce_two_units():
    text = (
        "This first complete sentence contains enough words to remain a legal standalone scene unit. "
        "This second complete sentence also contains enough words to remain a separate legal scene unit."
    )
    units = segment_voice_script(text)
    assert len(units) == 2


def test_long_multisentence_fixture_uses_real_sentence_boundaries():
    text = (
        "This first sentence has enough words to stand alone and should remain the first deterministic unit. "
        "This second sentence also has enough words to stand alone and should remain the second deterministic unit. "
        "This third sentence contains a natural comma boundary, plus enough additional words to push the sentence beyond the generation margin while preserving exact narration and source order."
    )
    units = segment_voice_script(text)
    assert len(units) >= 4
    assert units[0].startswith("This first sentence")
    assert units[1].startswith("This second sentence")
    assert normalize_narration(" ".join(units)) == normalize_narration(text)
    assert all(canonical_word_count(unit) <= 32 for unit in units)


def test_short_fragment_merge_prefers_28_before_32_fallback():
    prefix = " ".join(f"word{i}" for i in range(1, 27)) + "."
    text = prefix + " Ask first."
    units = segment_voice_script(text)
    assert len(units) == 1
    assert canonical_word_count(units[0]) == 28

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


def test_persisted_ledger_must_reconstruct_current_voice():
    voice = "Alpha narration has enough words here. Beta narration has enough words here."
    rows, _meta = build_scene_ledger(voice)
    assert validate_ledger_reconstruction(voice, rows) == []
    rows[0]["script_excerpt"] = "Mutated narration has enough words here."
    assert validate_ledger_reconstruction(voice, rows)


def test_avatar_and_notes_markers_cannot_bypass_merged_over_32_ceiling():
    first = "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen."
    second = "eighteen nineteen twenty twenty-one twenty-two twenty-three twenty-four twenty-five twenty-six twenty-seven twenty-eight twenty-nine thirty thirty-one thirty-two thirty-three thirty-four."
    ledger = _ledger(first, second)
    merged = first + " " + second
    prod = [{
        "scene_id": "SC001",
        "script_excerpt": merged,
        "recommended_asset_type": "AVATAR",
        "notes": "INTENTIONAL_LONG_AVATAR INTENTIONAL_EMPHASIS",
    }]
    issues = validate_production_against_ledger(prod, ledger)
    assert any("exceeds the ordinary 32-word Production ceiling" in issue for issue in issues)


def test_app_compiles_and_wires_ledger_gate_after_normalize_and_sanitize():
    import py_compile
    from pathlib import Path

    py_compile.compile("app.py", doraise=True)
    source = Path("app.py").read_text(encoding="utf-8")
    block_start = source.index("contract_ok, contract_issues = normalize_production_sheet")
    block_end = source.index("semantic_audit = None", block_start)
    block = source[block_start:block_end]
    assert block.index("sanitize_csv_file(") < block.index("production_sheet_ledger_issues(project)")
    assert "write_scene_ledger(project" in source


def test_legacy_normalization_path_cannot_bypass_ledger_acceptance_wiring():
    from pathlib import Path

    source = Path("app.py").read_text(encoding="utf-8")
    # normalize_production_sheet owns canonical/compact/legacy normalization; the
    # mandatory ledger gate is deliberately outside its branch and follows it.
    start = source.index("contract_ok, contract_issues = normalize_production_sheet")
    end = source.index("semantic_audit = None", start)
    acceptance = source[start:end]
    assert "production_sheet_ledger_issues(project)" in acceptance
    assert acceptance.index("normalize_production_sheet") < acceptance.index("production_sheet_ledger_issues(project)")


def test_agent_contract_requires_fresh_final_ids_after_legal_grouping():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]\n    agent = (root / "Agents" / "Production_Agent.md").read_text(encoding="utf-8")
    assert "regenerate scene_id, IMG001..IMGNNN, and BR001..BRNNN sequentially" in agent
    assert "no stale numbering" in agent

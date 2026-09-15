"""Canonical Runtime Lock: exactly one runtime authority, and runtime never drives content.

The failure this prevents: the writer-facing floor and the QA-facing floor were derived
from different WPM bases, so QA could mandate cuts and then demand back the same words —
an add-then-cut loop with no passing state for any draft.
"""

import json
from pathlib import Path

from v31_core import (
    DEFAULT_NARRATION_WPM,
    canonical_runtime,
    runtime_config_conflicts,
    runtime_within_canonical_range,
    validate_final_script,
)

ROOT = Path(__file__).resolve().parents[1]


def test_profile_is_derived_only_from_config() -> None:
    profile = canonical_runtime({
        "narration_words_per_minute": 150,
        "target_runtime_range_minutes": [18, 24],
        "target_runtime_minutes": 20,
    })
    assert profile.wpm == 150
    assert (profile.words_min, profile.words_max) == (2700, 3600)
    assert profile.words_target == 3000


def test_target_is_clamped_into_the_allowed_window() -> None:
    profile = canonical_runtime({
        "narration_words_per_minute": 150,
        "target_runtime_range_minutes": [18, 24],
        "target_runtime_minutes": 40,
    })
    assert profile.runtime_target == 24.0


def test_malformed_config_falls_back_to_one_shared_default() -> None:
    assert canonical_runtime({"narration_words_per_minute": "fast"}).wpm == DEFAULT_NARRATION_WPM
    assert canonical_runtime({}).wpm == DEFAULT_NARRATION_WPM


def test_within_range_is_the_runtime_pass_condition() -> None:
    config = {"narration_words_per_minute": 145, "target_runtime_range_minutes": [16, 35]}
    assert runtime_within_canonical_range(2720, config)
    assert not runtime_within_canonical_range(2000, config)
    assert not runtime_within_canonical_range(6000, config)


def test_script_validation_uses_the_canonical_profile() -> None:
    config = {"narration_words_per_minute": 150, "target_runtime_range_minutes": [18, 24]}
    validation = validate_final_script(ROOT / "does-not-exist", config)
    profile = canonical_runtime(config)
    assert (validation.target_words_min, validation.target_words_max) == (profile.words_min, profile.words_max)


def test_shipped_config_has_no_competing_runtime_authority() -> None:
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    conflicts = runtime_config_conflicts(config)
    assert not conflicts, f"a second runtime authority disagrees with config.json: {conflicts}"


def test_conflict_detector_actually_detects_a_second_authority(tmp_path: Path) -> None:
    system_dir = tmp_path / "System"
    system_dir.mkdir()
    (system_dir / "SYS_10_SCRIPT_STATE_MACHINE.json").write_text(json.dumps({
        "default_runtime": {
            "minimum_minutes": 18,
            "maximum_minutes": 23,
            "estimated_speaking_rate_wpm": {"default": 145},
        }
    }), encoding="utf-8")
    conflicts = runtime_config_conflicts(
        {"narration_words_per_minute": 169, "target_runtime_range_minutes": [19, 35]},
        system_dir=system_dir,
    )
    assert len(conflicts) == 2


def test_state_machine_defers_to_config() -> None:
    data = json.loads((ROOT / "System" / "SYS_10_SCRIPT_STATE_MACHINE.json").read_text(encoding="utf-8"))
    assert data["default_runtime"]["authority"].startswith("config.json")
    assert data["default_runtime"]["fallback_only"] is True
    lock = data["canonical_runtime_lock"]
    assert "SOURCE_POOL_EXHAUSTED" in lock["source_pool_exhaustion"]


def test_no_divergent_hardcoded_wpm_defaults_remain() -> None:
    for name in ("v31_core.py", "app.py"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert 'narration_words_per_minute", 150' not in text
        assert "narration_words_per_minute', 145" not in text
        assert 'narration_words_per_minute", 145' not in text


def test_narrative_prompt_surfaces_make_runtime_advisory_only() -> None:
    agent = (ROOT / "Agents" / "Narrative_QA_Agent.md").read_text(encoding="utf-8")
    opus = (ROOT / "Templates" / "Writing" / "opus_narrative_qa.md").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    template = (ROOT / "Templates" / "Writing" / "narrative_qa_output_template.md").read_text(encoding="utf-8")
    assert "RUNTIME ADVISORY-ONLY LOCK" in agent and "RUNTIME ADVISORY-ONLY LOCK" in app
    assert "Runtime Advisory — Non-Blocking" in opus
    assert "## Runtime Advisory" in template
    assert "There is no runtime PASS/FAIL status in Narrative QA" in agent
    assert "runtime is informational only" in opus.lower()
    assert "Runtime Shortfall Cause:" not in template
    assert "### Remaining Approved Material Audit" not in template


def test_agent_no_longer_routes_every_shortfall_to_the_writer() -> None:
    agent = (ROOT / "Agents" / "Narrative_QA_Agent.md").read_text(encoding="utf-8")
    assert "Return FAIL and route the script back to Writer/Outline for source-bounded redevelopment." not in agent

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "Agents" / "Thumbnail_Agent.md"
SYS06 = ROOT / "System" / "SYS_06_THUMBNAIL_ENGINE.json"
SYS11 = ROOT / "System" / "SYS_11_PIPELINE_DAG.json"
SYS12 = ROOT / "System" / "SYS_12_AGENTS.json"
SYS15 = ROOT / "System" / "SYS_15_VALIDATION_GATES.json"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _norm(label):
    label = label.lower().replace("/", " ")
    label = re.sub(r"[^a-z0-9]+", "_", label).strip("_")
    aliases = {
        "self_identification": "self_identification",
        "senior_comprehension_semantic_completeness": "senior_comprehension_semantic_completeness",
        "instant_visual_comprehension_renderability": "instant_visual_comprehension",
        "food_visibility_or_hero_object_clarity": "food_visibility",
    }
    return aliases.get(label, label)


def _metrics_from_instruction(agent, marker):
    matching = [line for line in agent.splitlines() if marker in line]
    assert len(matching) == 1, f"Expected one agent metric instruction containing {marker!r}; found {len(matching)}"
    payload = matching[0].split(marker, 1)[1].rstrip(".")
    parts = [x.strip() for x in payload.split(",")]
    if parts:
        parts[-1] = re.sub(r"^and\s+", "", parts[-1], flags=re.IGNORECASE)
    return [_norm(x) for x in parts]


def test_thumbnail_agent_metrics_match_sys06_authority():
    agent = AGENT.read_text(encoding="utf-8")
    sys06 = _load(SYS06)

    text_metrics = _metrics_from_instruction(agent, "For every text option, score ")
    assert text_metrics == sys06["thumbnail_text_intelligence"]["per_text_option_scoring"]["categories"]

    concept_metrics = _metrics_from_instruction(agent, "Score each concept using: ")
    sys06_concept_metrics = [item["id"] for item in sys06["scoring_model"]["categories"]]
    assert concept_metrics == sys06_concept_metrics
    assert sys06["scoring_model"]["total_score_max"] == 10 * len(sys06_concept_metrics)
    assert set(sys06["scoring_model"]["winner_minimums"]) <= set(sys06_concept_metrics)
    assert set(sys06["scoring_model"]["winner_text_minimums"]) <= set(
        sys06["thumbnail_text_intelligence"]["per_text_option_scoring"]["categories"]
    )


def test_thumbnail_registry_constraints_reference_existing_validators():
    sys06 = _load(SYS06)
    sys12 = _load(SYS12)
    thumb = next(a for a in sys12["agents"] if a["name"] == "thumbnail_agent")
    validator_ids = {v["id"] for v in sys06["validation_rules"]}

    for constraint in thumb["constraints"]:
        match = re.fullmatch(r"apply_V(\d+)_V(\d+)", constraint)
        assert match, f"Unsupported thumbnail constraint declaration: {constraint}"
        start, end = map(int, match.groups())
        assert {f"V{i}" for i in range(start, end + 1)} <= validator_ids

    declared_system_reads = {x for x in thumb["reads"] if x.startswith("SYS_")}
    agent = AGENT.read_text(encoding="utf-8")
    agent_system_reads = set(re.findall(r"System/(SYS_\d+)[^\x60]*\.json", agent))
    assert declared_system_reads == agent_system_reads


def test_thumbnail_prompt_is_required_across_pipeline_contracts():
    required = "Projects/<topic_slug>/11_thumbnail_prompt.md"
    sys06 = _load(SYS06)
    sys11 = _load(SYS11)
    sys12 = _load(SYS12)
    sys15 = _load(SYS15)

    assert sys06["required_outputs"]["required_prompt_file"] == required

    thumbnail_node = next(n for n in sys11["nodes"] if n["stage"] == "thumbnail")
    assert "11_thumbnail_prompt.md" in thumbnail_node["output"]

    thumb = next(a for a in sys12["agents"] if a["name"] == "thumbnail_agent")
    assert "11_thumbnail_prompt.md" in thumb["output_files"]

    assert required in sys15["validation_scopes"]["production_readiness"]["required_common_outputs"]


def test_thumbnail_v27_keeps_legacy_packages_version_aware():
    agent = AGENT.read_text(encoding="utf-8")
    sys06 = _load(SYS06)
    assert sys06["version"] == "2.7"
    assert sys06["output_contract"]["contract_version_marker"] == "Thumbnail Contract Version: 2.7"
    assert agent.count("Thumbnail Contract Version: 2.7") >= 2
    assert "If Thumbnail Contract Version is absent" in sys06["output_contract"]["legacy_detection_policy"]
    assert "2.6" in sys06["output_contract"]["legacy_detection_policy"]
    assert "Do not retroactively fail" in sys06["output_contract"]["legacy_project_policy"]


def test_thumbnail_machine_checked_strings_are_ascii_and_synced():
    agent = AGENT.read_text(encoding="utf-8")
    sys06 = _load(SYS06)
    fallback = sys06["reference_presenter_identity"]["fallback_when_reference_not_supplied"]["required_output_flag"]
    sync = sys06["output_contract"]["final_sync_line"]
    assert fallback == "PRESENTER_REFERENCE: NOT SUPPLIED - generic model used"
    assert sync == "Ranked-table <-> detailed-winner sync: PASS"
    assert fallback in agent
    assert sync in agent
    assert all(ord(ch) < 128 for ch in fallback + sync)


def test_thumbnail_v27_composition_has_no_fixed_43_41_tokens():
    active_paths = [
        AGENT,
        SYS06,
        ROOT / "Knowledge" / "06_Thumbnail_Blueprints.md",
        ROOT / "System" / "SYS_13_PROMPT_LIBRARY.json",
        ROOT / "app.py",
    ]
    for path in active_paths:
        text = path.read_text(encoding="utf-8")
        assert "43%" not in text, f"stale fixed composition token in {path}"
        assert "41%" not in text, f"stale fixed composition token in {path}"
        assert "left 43%" not in text.lower(), f"stale fixed left split in {path}"
        assert "maximum 41%" not in text.lower(), f"stale fixed text-width rule in {path}"
        assert "35–42%" not in text, f"stale fixed presenter-width rule in {path}"
        assert "35-42%" not in text, f"stale fixed presenter-width rule in {path}"
        assert "Maximum text width" not in text, f"stale maximum text width label in {path}"
        assert "Maximum text height" not in text, f"stale maximum text height label in {path}"
        assert "center-right" not in text, f"invalid 3x3 cell name in {path}"
        assert "\\u2194" not in text, f"non-ASCII sync arrow in {path}"


def test_thumbnail_v27_safe_zone_blocks_and_dominance_warns():
    sys06 = _load(SYS06)
    validators = {v["id"]: v for v in sys06["validation_rules"]}
    assert validators["V32"]["rule"] == "bottom_right_timestamp_safe_zone_clear"
    assert validators["V32"]["severity"] == "block"
    assert validators["V33"]["rule"] == "channel_led_text_visual_dominance"
    assert validators["V33"]["severity"] == "warn"
    assert sys06["composition_policy"]["bottom_right_timestamp_safe_zone"]["severity"] == "block"
    assert sys06["composition_policy"]["text_visual_dominance_guidance"]["severity"] == "warn"


def test_thumbnail_v27_safe_zone_machine_line_is_synced():
    agent = AGENT.read_text(encoding="utf-8")
    sys06 = _load(SYS06)
    line = sys06["output_contract"]["bottom_right_timestamp_safe_zone_line"]
    assert line == "Bottom-right timestamp safe zone: CLEAR"
    assert line in agent
    assert sys06["composition_policy"]["bottom_right_timestamp_safe_zone"]["required_output_line"] == line
    assert all(ord(ch) < 128 for ch in line)


def test_thumbnail_v27_grid_uses_only_declared_cell_names():
    sys06 = _load(SYS06)
    grid = sys06["composition_policy"]["grid_specification"]
    expected = {
        "top-left", "top-center", "top-right",
        "middle-left", "middle-center", "middle-right",
        "bottom-left", "bottom-center", "bottom-right",
    }
    assert set(grid["cell_names"]) == expected
    used = set(re.findall(r"(?:top|middle|bottom)-(?:left|center|right)", grid["example"]))
    assert used <= expected
    assert "center-right" not in grid["example"]


def test_thumbnail_v27_safe_zone_definition_is_consistent():
    agent = AGENT.read_text(encoding="utf-8")
    sys06 = _load(SYS06)
    zone = sys06["composition_policy"]["bottom_right_timestamp_safe_zone"]
    assert zone["prohibited"] == [
        "text", "face", "hands_or_gesture", "hero_object", "hero_group",
        "anatomical_illustration", "organ_cutaway", "internal_detail",
        "stool_cue", "card", "icon", "other_critical_detail"
    ]
    assert zone["allowed"] == ["background", "human_model_noncritical_clothing_or_shoulder"]
    v32 = next(v for v in sys06["validation_rules"] if v["id"] == "V32")
    for phrase in ("hands/gesture", "human model's non-critical clothing/shoulder", "anatomical illustrations", "stool cues"):
        assert phrase in v32["pass_condition"]
        assert phrase in agent
    assert "presenter torso/clothing" not in v32["pass_condition"]
    assert "presenter torso/clothing" not in agent
    assert "Tall-Hero Rule" in agent
    assert "tall_hero_rule" in sys06["composition_policy"]
    assert "Do not assign the hero and the face to the same column." in sys06["composition_policy"]["tall_hero_rule"]["rule"]


def test_thumbnail_v27_overlay_uses_grid_dimensions_not_percentage_width():
    sys06 = _load(SYS06)
    fields = sys06["text_overlay_specification"]["required_fields"]
    assert "maximum_text_width" not in fields
    assert "maximum_text_height" not in fields
    assert "text_width_grid_cells" in fields
    assert "text_height_grid_cells" in fields
    v31 = next(v for v in sys06["validation_rules"] if v["id"] == "V31")
    assert "text width grid cells" in v31["pass_condition"]
    assert "3x3 grid placement" in v31["pass_condition"]


def test_thumbnail_v27_generated_outputs_forbid_percentage_geometry_and_aliases():
    agent = AGENT.read_text(encoding="utf-8")
    sys06 = _load(SYS06)
    contract = sys06["composition_policy"]["output_geometry_contract"]
    assert contract["severity"].lower() == "block"
    assert contract["canonical_cell_names_only"] is True
    assert contract["aliases_invalid"] is True
    assert contract["required_grid_map_keys"] == ["text", "hero", "face", "bottom-right"]
    assert "Never express composition" in agent
    assert "numeric percentages" in agent
    assert "GRID MAP" in agent
    assert "Historical percentage geometry" in agent
    grid = sys06["composition_policy"]["grid_specification"]
    assert grid["required_grid_map"]["heading"] == "GRID MAP"
    assert grid["required_grid_map"]["keys"] == ["text", "hero", "face", "bottom-right"]
    v34 = next(v for v in sys06["validation_rules"] if v["id"] == "V34")
    assert v34["severity"] == "BLOCK"
    assert "no numeric composition percentages" in v34["pass_condition"]
    assert "non-canonical cell aliases" in v34["pass_condition"]


def test_thumbnail_v27_percentage_dominance_is_reviewer_only():
    sys06 = _load(SYS06)
    dominance = sys06["composition_policy"]["text_visual_dominance"]
    assert dominance["reviewer_only"] is True
    assert "Do not expose the numeric percentage target" in dominance["generated_output_rule"]

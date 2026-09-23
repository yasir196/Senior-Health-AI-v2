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


def _csv_after(agent, prefix):
    line = next(line for line in agent.splitlines() if line.startswith(prefix))
    payload = line.split(prefix, 1)[1].rstrip(".")
    parts = [x.strip() for x in payload.split(",")]
    if parts:
        parts[-1] = re.sub(r"^and\s+", "", parts[-1], flags=re.IGNORECASE)
    return [_norm(x) for x in parts]


def test_thumbnail_agent_metrics_match_sys06_authority():
    agent = AGENT.read_text(encoding="utf-8")
    sys06 = _load(SYS06)

    text_metrics = _csv_after(agent, "9. For every text option, score ")
    assert text_metrics == sys06["thumbnail_text_intelligence"]["per_text_option_scoring"]["categories"]

    concept_metrics = _csv_after(agent, "13. Score each concept using: ")
    sys06_concept_metrics = [item["id"] for item in sys06["scoring_model"]["categories"]]
    assert concept_metrics == sys06_concept_metrics
    assert sys06["scoring_model"]["total_score_max"] == 10 * len(sys06_concept_metrics)


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


def test_thumbnail_v26_keeps_legacy_packages_version_aware():
    sys06 = _load(SYS06)
    assert sys06["version"] == "2.6"
    policy = sys06["output_contract"]["legacy_project_policy"]
    assert "v2.5" in policy
    assert "Do not retroactively fail" in policy

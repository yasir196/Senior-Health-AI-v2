from pathlib import Path
import json

import v31_core
from evidence_depth import research_content_hash

ROOT=Path(__file__).resolve().parents[1]

def test_titles_stage_removed():
    assert "Titles" not in v31_core.WORKFLOW_STAGES
    assert all(stage != "Titles" for stage,_ in v31_core.PIPELINE)

def test_title_agent_removed_from_registry_and_dag():
    reg=json.loads((ROOT/"System/SYS_12_AGENTS.json").read_text(encoding="utf-8"))
    assert "title_agent" not in [a["name"] for a in reg["agents"]]
    dag=json.loads((ROOT/"System/SYS_11_PIPELINE_DAG.json").read_text(encoding="utf-8"))
    assert all(n.get("agent") != "title_agent" for n in dag["nodes"])

def test_downstream_uses_project_json_title():
    for rel in ["Agents/Thumbnail_Agent.md","Agents/Script_Agent.md","Agents/SEO_Agent.md"]:
        text=(ROOT/rel).read_text(encoding="utf-8")
        assert "project.json" in text
        assert "03_titles.md" not in text

def test_thumbnail_ready_without_generated_title_files(tmp_path):
    (tmp_path / "project.json").write_text(
        json.dumps({
            "topic": "My Exact Title",
            "anchor_title": "My Exact Title",
        }),
        encoding="utf-8",
    )
    (tmp_path / "01_topic_validation.md").write_text(
        "Status: PASS",
        encoding="utf-8",
    )
    (tmp_path / "02_research_sheet.md").write_text(
        "Research complete.",
        encoding="utf-8",
    )
    (tmp_path / "13_fact_check_log.md").write_text(
        "Gate reviewed: Gate 1\nOverall status: PASS\n",
        encoding="utf-8",
    )

    contract = json.loads(
        (ROOT / "System/SYS_19_EVIDENCE_DEPTH_DIMENSIONS.json").read_text(
            encoding="utf-8"
        )
    )

    dimensions = []
    for name in contract["baseline_dimensions"]:
        if name == "core_proposition":
            dimensions.append({
                "dimension": name,
                "status": "supported",
                "rationale": "Core proposition supported.",
                "proposition_ids": ["P1"],
            })
        else:
            dimensions.append({
                "dimension": name,
                "status": "not_applicable",
                "rationale": "Not applicable to this fixture.",
                "proposition_ids": [],
            })

    research = {
        "schema_version": "research-claims-v1",
        "dimensions_contract_version": contract["version"],
        "canonicalization_version": contract["canonicalization"]["version"],
        "applicable_topic_tags": [],
        "research_content_hash": "",
        "dimensions": dimensions,
        "propositions": [{
            "proposition_id": "P1",
            "dimension": "core_proposition",
            "proposition": "Fixture proposition.",
            "status": "supported",
            "evidence_source_ids": ["SRC_KIWI_USDA_FDC"],
            "material_source_ids": ["SRC_KIWI_USDA_FDC"],
            "counterevidence_searched": True,
            "counterevidence_found": False,
            "resulting_qualification": "None required.",
            "saturation_note": "Relevant evidence considered.",
        }],
        "claims": [],
    }

    research["research_content_hash"] = research_content_hash(
        research,
        contract,
    )

    (tmp_path / "02_research_claims.json").write_text(
        json.dumps(research),
        encoding="utf-8",
    )

    disposition = {
        "schema_version": contract["gate1_binding"]["schema_version"],
        "research_artifact_hash": research_content_hash(research, contract),
        "canonicalization_version": contract["canonicalization"]["version"],
        "claim_dispositions": [],
    }
    (tmp_path / "13_gate1_disposition.json").write_text(
        json.dumps(disposition),
        encoding="utf-8",
    )

    ready, reasons = v31_core.stage_ready(
        tmp_path,
        "Thumbnail",
        {},
    )

    assert ready, reasons
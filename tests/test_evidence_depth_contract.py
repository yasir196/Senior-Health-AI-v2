import copy
import json
from pathlib import Path

from evidence_depth import (
    CORE_INSUFFICIENT,
    HUMAN_DECISION_REQUIRED,
    gate1_is_current,
    research_content_hash,
    validate_research_artifact,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "System" / "SYS_19_EVIDENCE_DEPTH_DIMENSIONS.json").read_text(encoding="utf-8"))


def artifact():
    dims = []
    for name in CONTRACT["baseline_dimensions"]:
        if name == "core_proposition":
            dims.append({"dimension": name, "status": "supported", "proposition_ids": ["P1"]})
        else:
            dims.append({"dimension": name, "status": "not_applicable", "rationale": "Not material to this approved angle."})
    return {
        "schema_version": "research-claims-v1",
        "dimensions_contract_version": CONTRACT["version"],
        "canonicalization_version": CONTRACT["canonicalization"]["version"],
        "applicable_topic_tags": [],
        "dimensions": dims,
        "propositions": [{
            "proposition_id": "P1",
            "text": "Bounded core proposition",
            "evidence_source_ids": ["SRC1"],
            "counterevidence_searched": True,
            "counterevidence_found": [],
            "resulting_qualification": "Bounded to the evidence.",
            "saturation_note": "Further searching yielded no materially new distinction."
        }],
        "claims": []
    }


def test_small_saturated_evidence_base_can_pass_without_numeric_quota():
    a = artifact()
    a["research_content_hash"] = research_content_hash(a, CONTRACT)
    status, errors = validate_research_artifact(a, CONTRACT)
    assert status == "PASS", errors


def test_dimension_addressal_does_not_require_dimension_fabrication():
    a = artifact()
    mechanism = next(d for d in a["dimensions"] if d["dimension"] == "mechanism_context")
    mechanism.clear()
    mechanism.update({"dimension": "mechanism_context", "status": "no_evidence_found", "search_note": "No material mechanism evidence found."})
    a["research_content_hash"] = research_content_hash(a, CONTRACT)
    status, errors = validate_research_artifact(a, CONTRACT)
    assert status == "PASS", errors


def test_invented_unsupported_proposition_fails():
    a = artifact()
    a["propositions"].append({
        "proposition_id": "P2", "text": "Padding proposition", "evidence_source_ids": [],
        "counterevidence_searched": True, "counterevidence_found": [],
        "resulting_qualification": "None", "saturation_note": "Added for breadth"
    })
    status, errors = validate_research_artifact(a, CONTRACT)
    assert status == "FAIL"
    assert any("P2" in e and "evidence_source_ids" in e for e in errors)


def test_partial_support_requires_explicit_boundary():
    a = artifact()
    core = next(d for d in a["dimensions"] if d["dimension"] == "core_proposition")
    core["status"] = "partially_supported"
    status, errors = validate_research_artifact(a, CONTRACT)
    assert status == "FAIL"
    assert any("support_boundary" in e for e in errors)


def test_core_without_evidence_requires_terminal_human_decision():
    a = artifact()
    core = next(d for d in a["dimensions"] if d["dimension"] == "core_proposition")
    core.clear()
    core.update({"dimension": "core_proposition", "status": "no_evidence_found", "search_note": "Searched; no support."})
    status, errors = validate_research_artifact(a, CONTRACT)
    assert status == HUMAN_DECISION_REQUIRED
    assert errors == [CORE_INSUFFICIENT]


def test_canonical_hash_ignores_volatile_metadata_and_key_order():
    a = artifact()
    b = copy.deepcopy(a)
    a["generated_at"] = "2026-01-01T00:00:00"
    b["generated_at"] = "2026-09-17T12:00:00"
    b["applicable_topic_tags"] = list(reversed(b["applicable_topic_tags"]))
    assert research_content_hash(a, CONTRACT) == research_content_hash(b, CONTRACT)


def test_research_change_makes_gate1_disposition_stale():
    a = artifact()
    disposition = {"research_artifact_hash": research_content_hash(a, CONTRACT)}
    assert gate1_is_current(a, disposition, CONTRACT)
    a["propositions"][0]["resulting_qualification"] = "Changed boundary"
    assert not gate1_is_current(a, disposition, CONTRACT)


def test_metadata_incomplete_claim_cannot_be_production_usable():
    a = artifact()
    a["claims"] = [{"claim_id": "C1", "population_metadata_status": "metadata_incomplete", "usable_for_production": True}]
    status, errors = validate_research_artifact(a, CONTRACT)
    assert status == "FAIL"
    assert any("incomplete population metadata" in e for e in errors)


def test_contract_contains_no_numeric_source_or_claim_floor():
    text = json.dumps(CONTRACT).lower()
    assert "minimum source" not in text
    assert "minimum claim" not in text
    assert "min_sources" not in text
    assert "min_claims" not in text

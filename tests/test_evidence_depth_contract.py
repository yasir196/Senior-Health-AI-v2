import copy
import json
from pathlib import Path

from evidence_depth import (
    CORE_INSUFFICIENT,
    HUMAN_DECISION_REQUIRED,
    gate1_is_current,
    load_evidence_context,
    research_content_hash,
    validate_research_artifact,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "System" / "SYS_19_EVIDENCE_DEPTH_DIMENSIONS.json").read_text(encoding="utf-8"))
EVIDENCE_LIBRARY, SOURCE_TYPES = load_evidence_context(ROOT)


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


def finalize(a):
    a["research_content_hash"] = research_content_hash(a, CONTRACT)
    return a


def outcome_claim(**overrides):
    claim = {
        "claim_id": "C1",
        "evidence_applicability_type": "outcome_study",
        "material_source_ids": ["SRC_SLEEP_KIWI_2011"],
        "study_population": "Adults ages 20-55",
        "target_population": "Adults 60+",
        "senior_specific": False,
        "extrapolation_caveat": "Evidence is not senior-specific.",
        "population_metadata_status": "complete",
        "usable_for_production": True,
    }
    claim.update(overrides)
    return claim


def validate(a):
    return validate_research_artifact(a, CONTRACT, EVIDENCE_LIBRARY, SOURCE_TYPES)


def test_small_saturated_evidence_base_can_pass_without_numeric_quota():
    status, errors = validate(finalize(artifact()))
    assert status == "PASS", errors


def test_dimension_addressal_does_not_require_dimension_fabrication():
    a = artifact()
    mechanism = next(d for d in a["dimensions"] if d["dimension"] == "mechanism_context")
    mechanism.clear()
    mechanism.update({"dimension": "mechanism_context", "status": "no_evidence_found", "search_note": "No material mechanism evidence found."})
    status, errors = validate(finalize(a))
    assert status == "PASS", errors


def test_invented_unsupported_proposition_fails():
    a = artifact()
    a["propositions"].append({
        "proposition_id": "P2", "text": "Padding proposition", "evidence_source_ids": [],
        "counterevidence_searched": True, "counterevidence_found": [],
        "resulting_qualification": "None", "saturation_note": "Added for breadth"
    })
    status, errors = validate(finalize(a))
    assert status == "FAIL"
    assert any("P2" in e and "evidence_source_ids" in e for e in errors)


def test_partial_support_requires_explicit_boundary():
    a = artifact()
    core = next(d for d in a["dimensions"] if d["dimension"] == "core_proposition")
    core["status"] = "partially_supported"
    status, errors = validate(finalize(a))
    assert status == "FAIL"
    assert any("support_boundary" in e for e in errors)


def test_core_without_evidence_requires_terminal_human_decision_and_keeps_other_errors():
    a = artifact()
    core = next(d for d in a["dimensions"] if d["dimension"] == "core_proposition")
    core.clear()
    core.update({"dimension": "core_proposition", "status": "no_evidence_found", "search_note": "Searched; no support."})
    a["propositions"][0]["saturation_note"] = ""
    status, errors = validate(finalize(a))
    assert status == HUMAN_DECISION_REQUIRED
    assert CORE_INSUFFICIENT in errors
    assert any("saturation_note" in e for e in errors)


def test_missing_core_dimension_uses_same_terminal_human_state_not_research_fail_loop():
    a = artifact()
    a["dimensions"] = [d for d in a["dimensions"] if d["dimension"] != "core_proposition"]
    status, errors = validate(finalize(a))
    assert status == HUMAN_DECISION_REQUIRED
    assert CORE_INSUFFICIENT in errors
    assert any("missing required dimensions" in e for e in errors)


def test_canonical_hash_ignores_volatile_metadata_and_self_hash():
    a = artifact()
    b = copy.deepcopy(a)
    a["generated_at"] = "2026-01-01T00:00:00"
    b["generated_at"] = "2026-09-17T12:00:00"
    b["research_content_hash"] = "sha256:decorative-placeholder"
    assert research_content_hash(a, CONTRACT) == research_content_hash(b, CONTRACT)


def test_research_change_makes_gate1_disposition_stale():
    a = artifact()
    disposition = {"research_artifact_hash": research_content_hash(a, CONTRACT)}
    assert gate1_is_current(a, disposition, CONTRACT)
    a["propositions"][0]["resulting_qualification"] = "Changed boundary"
    assert not gate1_is_current(a, disposition, CONTRACT)


def test_metadata_incomplete_claim_requires_explicit_nonusable_state():
    a = artifact()
    a["claims"] = [outcome_claim(population_metadata_status="metadata_incomplete", study_population=None, senior_specific=None, usable_for_production=True)]
    status, errors = validate(finalize(a))
    assert status == "FAIL"
    assert any("requires usable_for_production=false" in e for e in errors)


def test_missing_usable_for_production_does_not_default_permissive():
    a = artifact()
    claim = outcome_claim()
    del claim["usable_for_production"]
    a["claims"] = [claim]
    status, errors = validate(finalize(a))
    assert status == "FAIL"
    assert any("usable_for_production" in e for e in errors)


def test_declared_lower_precedence_type_cannot_downgrade_outcome_source():
    a = artifact()
    a["claims"] = [outcome_claim(evidence_applicability_type="descriptive_compositional", study_population=None, senior_specific=None, extrapolation_caveat=None)]
    status, errors = validate(finalize(a))
    assert status == "FAIL"
    assert any("does not match governing type 'outcome_study'" in e for e in errors)


def test_unmapped_source_type_blocks_claim():
    a = artifact()
    a["claims"] = [outcome_claim(material_source_ids=["SRC_UNKNOWN"])]
    status, errors = validate_research_artifact(a, CONTRACT, EVIDENCE_LIBRARY, {**SOURCE_TYPES, "SRC_UNKNOWN": "mystery evidence"})
    assert status == "FAIL"
    assert any("unmapped source_type" in e for e in errors)


def test_outcome_complete_requires_study_population_and_senior_boolean():
    a = artifact()
    a["claims"] = [outcome_claim(study_population=None, senior_specific=None)]
    status, errors = validate(finalize(a))
    assert status == "FAIL"
    assert any("requires study_population" in e for e in errors)
    assert any("requires senior_specific boolean" in e for e in errors)


def test_non_senior_outcome_to_senior_target_requires_extrapolation_caveat():
    a = artifact()
    a["claims"] = [outcome_claim(extrapolation_caveat=None)]
    status, errors = validate(finalize(a))
    assert status == "FAIL"
    assert any("requires extrapolation_caveat" in e for e in errors)


def test_guideline_and_compositional_null_rules_are_enforced():
    a = artifact()
    a["claims"] = [{
        "claim_id": "G1", "evidence_applicability_type": "guideline", "material_source_ids": ["SRC_SLEEP_AASM_2021"],
        "study_population": "should be null", "target_population": "Adults", "senior_specific": False,
        "extrapolation_caveat": None, "population_metadata_status": "complete", "usable_for_production": True,
    }]
    status, errors = validate(finalize(a))
    assert status == "FAIL"
    assert any("guideline requires study_population=null" in e for e in errors)

    b = artifact()
    b["claims"] = [{
        "claim_id": "D1", "evidence_applicability_type": "descriptive_compositional", "material_source_ids": ["SRC_KIWI_USDA_FDC"],
        "study_population": None, "target_population": "Adults 60+", "senior_specific": False,
        "extrapolation_caveat": "not allowed", "population_metadata_status": "complete", "usable_for_production": True,
    }]
    status, errors = validate(finalize(b))
    assert status == "FAIL"
    assert any("senior_specific=null" in e for e in errors)
    assert any("extrapolation_caveat=null" in e for e in errors)


def test_contract_contains_no_numeric_source_or_claim_floor():
    text = json.dumps(CONTRACT).lower()
    assert "minimum source" not in text
    assert "minimum claim" not in text
    assert "min_sources" not in text
    assert "min_claims" not in text

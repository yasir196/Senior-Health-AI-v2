import copy
import json
from pathlib import Path

from evidence_depth import (
    CORE_INSUFFICIENT,
    HUMAN_DECISION_REQUIRED,
    gate1_is_current,
    load_evidence_context,
    research_content_hash,
    research_gate1_readiness,
    validate_gate1_disposition,
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


def gate1_artifact():
    a = artifact()
    a["claims"] = [outcome_claim()]
    return finalize(a)


def gate1_disposition(a, **item_overrides):
    item = {
        "claim_id": "C1",
        "disposition": "approved",
        "medical_notes": "Claim is medically usable within the Research boundary.",
    }
    item.update(item_overrides)
    return {
        "schema_version": CONTRACT["gate1_binding"]["schema_version"],
        "research_artifact_hash": research_content_hash(a, CONTRACT),
        "canonicalization_version": CONTRACT["canonicalization"]["version"],
        "claim_dispositions": [item],
    }


def test_valid_gate1_disposition_covers_current_research_claims():
    a = gate1_artifact()
    errors = validate_gate1_disposition(a, gate1_disposition(a), CONTRACT)
    assert errors == []


def test_gate1_disposition_rejects_stale_research_hash():
    a = gate1_artifact()
    disposition = gate1_disposition(a)
    disposition["research_artifact_hash"] = "sha256:stale"
    errors = validate_gate1_disposition(a, disposition, CONTRACT)
    assert any("stale" in e for e in errors)


def test_gate1_disposition_requires_matching_canonicalization_version():
    a = gate1_artifact()
    disposition = gate1_disposition(a)
    disposition["canonicalization_version"] = "wrong-version"
    errors = validate_gate1_disposition(a, disposition, CONTRACT)
    assert any("canonicalization_version" in e for e in errors)

def test_gate1_disposition_requires_schema_version():
    a = gate1_artifact()
    disposition = gate1_disposition(a)
    disposition.pop("schema_version")

    errors = validate_gate1_disposition(a, disposition, CONTRACT)

    assert any("schema_version" in e for e in errors)

def test_gate1_disposition_requires_every_research_claim():
    a = gate1_artifact()
    disposition = gate1_disposition(a)
    disposition["claim_dispositions"] = []
    errors = validate_gate1_disposition(a, disposition, CONTRACT)
    assert any("missing Research claim IDs" in e and "C1" in e for e in errors)


def test_gate1_disposition_rejects_duplicate_and_unknown_claim_ids():
    a = gate1_artifact()
    disposition = gate1_disposition(a)
    disposition["claim_dispositions"] = [
        {
            "claim_id": "C1",
            "disposition": "approved",
            "medical_notes": "First disposition.",
        },
        {
            "claim_id": "C1",
            "disposition": "approved",
            "medical_notes": "Duplicate disposition.",
        },
        {
            "claim_id": "UNKNOWN",
            "disposition": "rejected",
            "medical_notes": "Unknown claim.",
        },
    ]
    errors = validate_gate1_disposition(a, disposition, CONTRACT)
    assert any("Duplicate" in e and "C1" in e for e in errors)
    assert any("unknown claim_id UNKNOWN" in e for e in errors)


def test_gate1_disposition_rejects_invalid_disposition_value():
    a = gate1_artifact()
    disposition = gate1_disposition(a, disposition="needs_revision")
    errors = validate_gate1_disposition(a, disposition, CONTRACT)
    assert any("invalid disposition" in e for e in errors)


def test_bounded_gate1_claim_requires_wording_or_boundary():
    a = gate1_artifact()
    disposition = gate1_disposition(a, disposition="bounded")
    errors = validate_gate1_disposition(a, disposition, CONTRACT)
    assert any("requires bounded wording or boundary" in e for e in errors)


def test_bounded_gate1_claim_accepts_explicit_boundary():
    a = gate1_artifact()
    disposition = gate1_disposition(
        a,
        disposition="bounded",
        boundary="Use only the qualified Research wording.",
    )
    errors = validate_gate1_disposition(a, disposition, CONTRACT)
    assert errors == []


def test_gate1_claim_requires_medical_notes():
    a = gate1_artifact()
    disposition = gate1_disposition(a, medical_notes="")
    errors = validate_gate1_disposition(a, disposition, CONTRACT)
    assert any("requires concise medical notes" in e for e in errors)

def test_terminal_core_state_survives_missing_gate1_artifacts(tmp_path):
    a = artifact()

    core = next(
        d for d in a["dimensions"]
        if d["dimension"] == "core_proposition"
    )
    core.clear()
    core.update({
        "dimension": "core_proposition",
        "status": "no_evidence_found",
        "search_note": "Searched; no adequate support found.",
    })

    finalize(a)

    (tmp_path / "02_research_sheet.md").write_text(
        "Research complete.",
        encoding="utf-8",
    )
    (tmp_path / "02_research_claims.json").write_text(
        json.dumps(a),
        encoding="utf-8",
    )

    status, errors = research_gate1_readiness(tmp_path, ROOT)

    assert status == HUMAN_DECISION_REQUIRED
    assert CORE_INSUFFICIENT in errors
    assert not any(
        "13_gate1_disposition.json is missing" in e
        for e in errors
    )
    assert not any(
        "13_fact_check_log.md is missing" in e
        for e in errors
    )

def test_ordinary_research_pass_still_requires_gate1_artifacts(tmp_path):
    a = finalize(artifact())

    (tmp_path / "02_research_sheet.md").write_text(
        "Research complete.",
        encoding="utf-8",
    )
    (tmp_path / "02_research_claims.json").write_text(
        json.dumps(a),
        encoding="utf-8",
    )

    status, errors = research_gate1_readiness(tmp_path, ROOT)

    assert status == "FAIL"
    assert any(
        "13_gate1_disposition.json is missing" in e
        for e in errors
    )
    assert any(
        "13_fact_check_log.md is missing" in e
        for e in errors
    )

def test_research_gate1_readiness_rejects_empty_fact_check_log(tmp_path):
    a = gate1_artifact()

    (tmp_path / "02_research_sheet.md").write_text(
        "Research sheet",
        encoding="utf-8",
    )
    (tmp_path / "02_research_claims.json").write_text(
        json.dumps(a),
        encoding="utf-8",
    )
    (tmp_path / "13_gate1_disposition.json").write_text(
        json.dumps(gate1_disposition(a)),
        encoding="utf-8",
    )
    (tmp_path / "13_fact_check_log.md").write_text("", encoding="utf-8")

    status, errors = research_gate1_readiness(tmp_path, ROOT)

    assert status == "FAIL"
    assert any("13_fact_check_log.md is empty" in e for e in errors)


def test_research_gate1_readiness_passes_valid_structured_handoff(tmp_path):
    a = gate1_artifact()

    (tmp_path / "02_research_sheet.md").write_text(
        "Research sheet",
        encoding="utf-8",
    )
    (tmp_path / "02_research_claims.json").write_text(
        json.dumps(a),
        encoding="utf-8",
    )
    (tmp_path / "13_gate1_disposition.json").write_text(
        json.dumps(gate1_disposition(a)),
        encoding="utf-8",
    )
    (tmp_path / "13_fact_check_log.md").write_text(
        "Gate reviewed: Gate 1\nOverall status: PASS\n",
        encoding="utf-8",
    )

    status, errors = research_gate1_readiness(tmp_path, ROOT)

    assert status == "PASS"
    assert errors == []
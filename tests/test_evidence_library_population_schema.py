import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_claim_registry_has_additive_population_columns_and_seven_rows():
    with (ROOT / "Evidence" / "claim_registry.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 7
    required = {
        "evidence_applicability_type", "material_source_ids", "study_population",
        "target_population", "senior_specific", "extrapolation_caveat",
        "population_metadata_status", "source_identity_status",
    }
    assert required.issubset(rows[0])
    assert all(row["source_identity_status"] == "unresolved" for row in rows)
    assert not any(row["senior_specific"].strip().lower() == "true" for row in rows)


def test_kiwi_sleep_reuse_carries_explicit_non_senior_population_caveat():
    with (ROOT / "Evidence" / "claim_registry.csv").open(encoding="utf-8", newline="") as handle:
        rows = {row["claim_id"]: row for row in csv.DictReader(handle)}
    row = rows["CLM_KIWI_SLEEP_ROUTINE"]
    assert row["evidence_applicability_type"] == "outcome_study"
    assert row["study_population"]
    assert row["senior_specific"].lower() == "false"
    assert row["extrapolation_caveat"]
    assert row["population_metadata_status"] == "complete"


def test_missing_repo_population_metadata_is_not_silently_inferred():
    with (ROOT / "Evidence" / "claim_registry.csv").open(encoding="utf-8", newline="") as handle:
        rows = {row["claim_id"]: row for row in csv.DictReader(handle)}
    for claim_id in ("CLM_KIWI_ALLERGY_CAVEAT", "CLM_DASH_BP_SUPPORT", "CLM_DASH_SODIUM_BP", "CLM_OATS_CVD_SUPPORT"):
        assert rows[claim_id]["population_metadata_status"] == "metadata_incomplete"
        assert not rows[claim_id]["study_population"]


def test_sys18_preserves_sys09_authority_and_has_no_generic_null_escape():
    contract = json.loads((ROOT / "System" / "SYS_18_EVIDENCE_LIBRARY.json").read_text(encoding="utf-8"))
    assert "System/SYS_09_MEDICAL_RULE_ENGINE.json" in contract["immutability_boundary"]["cannot_modify"]
    assert "no generic null escape" in contract["null_semantics"].lower()

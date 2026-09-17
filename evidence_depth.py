from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

HUMAN_DECISION_REQUIRED = "HUMAN_DECISION_REQUIRED"
CORE_INSUFFICIENT = "CORE_PROPOSITION_INSUFFICIENT_EVIDENCE"


def _normalize(value: Any, *, set_like_keys: set[str], key: str = "") -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, dict):
        return {k: _normalize(value[k], set_like_keys=set_like_keys, key=k) for k in sorted(value)}
    if isinstance(value, list):
        normalized = [_normalize(v, set_like_keys=set_like_keys) for v in value]
        if key in set_like_keys:
            return sorted(normalized, key=lambda v: json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return normalized
    return value


def canonical_research_payload(artifact: dict[str, Any], contract: dict[str, Any]) -> bytes:
    canon = contract["canonicalization"]
    excluded = set(canon.get("volatile_fields", [])) | set(canon.get("self_excluded_fields", []))
    set_like = set(canon.get("set_like_arrays", []))
    semantic = {k: v for k, v in artifact.items() if k not in excluded}
    normalized = _normalize(semantic, set_like_keys=set_like)
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def research_content_hash(artifact: dict[str, Any], contract: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_research_payload(artifact, contract)).hexdigest()


def expected_dimensions(contract: dict[str, Any], topic_tags: list[str]) -> set[str]:
    result = set(contract.get("baseline_dimensions", []))
    extensions = contract.get("topic_extensions", {})
    for tag in topic_tags:
        result.update(extensions.get(tag, []))
    return result


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_null(value: Any) -> bool:
    return value is None or value == ""


def _senior_facing(target_population: Any) -> bool:
    if not isinstance(target_population, str):
        return False
    text = target_population.lower()
    return bool(re.search(r"\b(senior|seniors|older adult|older adults|elderly)\b", text) or re.search(r"\b(?:5[5-9]|[6-9]\d)\s*\+", text))


def _governing_type(
    claim: dict[str, Any],
    evidence_library: dict[str, Any],
    source_type_by_id: dict[str, str],
) -> tuple[str | None, list[str]]:
    errors: list[str] = []
    material_ids = claim.get("material_source_ids") or []
    if isinstance(material_ids, str):
        material_ids = [part.strip() for part in material_ids.split(";") if part.strip()]
    if not material_ids:
        return None, [f"{claim.get('claim_id','claim')}: material_source_ids is required"]

    source_type_map = evidence_library.get("source_type_map", {})
    precedence = evidence_library.get("evidence_applicability_types", {}).get("precedence", [])
    rank = {name: index for index, name in enumerate(precedence)}
    mapped: list[str] = []
    for source_id in material_ids:
        raw_type = source_type_by_id.get(source_id)
        if raw_type is None:
            errors.append(f"{claim.get('claim_id','claim')}: material source {source_id} is missing from evidence_sources.csv")
            continue
        applicability_type = source_type_map.get(raw_type)
        if applicability_type is None:
            errors.append(f"{claim.get('claim_id','claim')}: unmapped source_type {raw_type!r} for {source_id}")
            continue
        if applicability_type not in rank:
            errors.append(f"{claim.get('claim_id','claim')}: mapped applicability type {applicability_type!r} is absent from precedence")
            continue
        mapped.append(applicability_type)
    if errors or not mapped:
        return None, errors
    return min(mapped, key=lambda value: rank[value]), []


def _validate_population_claim(
    claim: dict[str, Any],
    evidence_library: dict[str, Any],
    source_type_by_id: dict[str, str],
) -> list[str]:
    errors: list[str] = []
    claim_id = claim.get("claim_id", "claim")
    for field in evidence_library.get("research_claim_required_fields", []):
        if field not in claim:
            errors.append(f"{claim_id}: missing required safety field {field}")

    declared_type = claim.get("evidence_applicability_type")
    governing_type, type_errors = _governing_type(claim, evidence_library, source_type_by_id)
    errors.extend(type_errors)
    if governing_type is not None and declared_type != governing_type:
        errors.append(f"{claim_id}: declared evidence_applicability_type {declared_type!r} does not match governing type {governing_type!r}")

    rules = evidence_library.get("type_governed_population_rules", {})
    if declared_type not in rules:
        errors.append(f"{claim_id}: invalid evidence_applicability_type {declared_type!r}")
        return errors

    metadata_status = claim.get("population_metadata_status")
    if metadata_status not in evidence_library.get("population_metadata_status_values", []):
        errors.append(f"{claim_id}: population_metadata_status is required and must be valid")
    usable = claim.get("usable_for_production")
    if not isinstance(usable, bool):
        errors.append(f"{claim_id}: usable_for_production must be an explicit boolean")
    if metadata_status == "metadata_incomplete" and usable is not False:
        errors.append(f"{claim_id}: incomplete population metadata requires usable_for_production=false")

    study_population = claim.get("study_population")
    target_population = claim.get("target_population")
    senior_specific = claim.get("senior_specific")
    extrapolation = claim.get("extrapolation_caveat")

    if not _nonempty(target_population):
        errors.append(f"{claim_id}: target_population is required")

    if declared_type == "outcome_study":
        if metadata_status == "complete" and not _nonempty(study_population):
            errors.append(f"{claim_id}: outcome_study requires study_population when metadata is complete")
        if metadata_status == "complete" and not isinstance(senior_specific, bool):
            errors.append(f"{claim_id}: outcome_study requires senior_specific boolean when metadata is complete")
        if senior_specific is False and _senior_facing(target_population) and not _nonempty(extrapolation):
            errors.append(f"{claim_id}: non-senior outcome evidence used for a senior-facing target requires extrapolation_caveat")
    elif declared_type == "guideline":
        if not _is_null(study_population):
            errors.append(f"{claim_id}: guideline requires study_population=null")
        if not isinstance(senior_specific, bool):
            errors.append(f"{claim_id}: guideline requires explicit senior_specific boolean based on guideline scope")
    elif declared_type == "descriptive_compositional":
        if not _is_null(study_population):
            errors.append(f"{claim_id}: descriptive_compositional requires study_population=null")
        if not _is_null(senior_specific):
            errors.append(f"{claim_id}: descriptive_compositional requires senior_specific=null")
        if not _is_null(extrapolation):
            errors.append(f"{claim_id}: descriptive_compositional requires extrapolation_caveat=null")
    return errors


def validate_research_artifact(
    artifact: dict[str, Any],
    contract: dict[str, Any],
    evidence_library: dict[str, Any] | None = None,
    source_type_by_id: dict[str, str] | None = None,
) -> tuple[str, list[str]]:
    errors: list[str] = []
    for field in contract.get("artifact_binding", {}).get("required_artifact_fields", []):
        if field not in artifact:
            errors.append(f"missing required artifact field: {field}")
    if artifact.get("dimensions_contract_version") != contract.get("version"):
        errors.append("dimensions_contract_version does not match the loaded contract")
    if artifact.get("canonicalization_version") != contract.get("canonicalization", {}).get("version"):
        errors.append("canonicalization_version does not match the loaded contract")

    tags = artifact.get("applicable_topic_tags") or []
    dims = {d.get("dimension"): d for d in artifact.get("dimensions", []) if isinstance(d, dict) and d.get("dimension")}
    missing = sorted(expected_dimensions(contract, tags) - set(dims))
    if missing:
        errors.append("missing required dimensions: " + ", ".join(missing))

    allowed_status = set(contract.get("dimension_status_values", []))
    propositions = {p.get("proposition_id"): p for p in artifact.get("propositions", []) if isinstance(p, dict) and p.get("proposition_id")}
    for name, dim in dims.items():
        status = dim.get("status")
        if status not in allowed_status:
            errors.append(f"{name}: invalid dimension status")
            continue
        linked = dim.get("proposition_ids") or []
        if status in {"supported", "partially_supported"}:
            if not linked or any(pid not in propositions for pid in linked):
                errors.append(f"{name}: supported status requires mapped propositions")
            if status == "partially_supported" and not _nonempty(dim.get("support_boundary")):
                errors.append(f"{name}: partially_supported requires support_boundary")
        elif status == "no_evidence_found" and not _nonempty(dim.get("search_note")):
            errors.append(f"{name}: no_evidence_found requires search_note")
        elif status == "not_applicable" and not _nonempty(dim.get("rationale")):
            errors.append(f"{name}: not_applicable requires rationale")

    core = dims.get("core_proposition")
    core_requires_human = not isinstance(core, dict) or core.get("status") not in {"supported", "partially_supported"}
    if core_requires_human and CORE_INSUFFICIENT not in errors:
        errors.append(CORE_INSUFFICIENT)

    for pid, prop in propositions.items():
        evidence_ids = prop.get("evidence_source_ids") or []
        if not evidence_ids:
            errors.append(f"{pid}: material proposition requires evidence_source_ids")
        if prop.get("counterevidence_searched") is not True:
            errors.append(f"{pid}: counterevidence_searched must be true")
        if "counterevidence_found" not in prop:
            errors.append(f"{pid}: counterevidence_found must be recorded")
        if not _nonempty(prop.get("resulting_qualification")):
            errors.append(f"{pid}: resulting_qualification is required")
        if not _nonempty(prop.get("saturation_note")):
            errors.append(f"{pid}: saturation_note is required")

    claims = artifact.get("claims") or []
    if claims and (evidence_library is None or source_type_by_id is None):
        errors.append("claim validation requires SYS_18 and evidence source-type context")
    else:
        for claim in claims:
            if not isinstance(claim, dict):
                errors.append("claim entry must be an object")
                continue
            errors.extend(_validate_population_claim(claim, evidence_library or {}, source_type_by_id or {}))

    expected_hash = research_content_hash(artifact, contract)
    recorded = artifact.get("research_content_hash")
    if recorded and recorded != expected_hash:
        errors.append("research_content_hash does not match canonical content")

    if core_requires_human:
        return HUMAN_DECISION_REQUIRED, errors
    return ("FAIL", errors) if errors else ("PASS", [])


def gate1_is_current(research_artifact: dict[str, Any], disposition: dict[str, Any], contract: dict[str, Any]) -> bool:
    return disposition.get("research_artifact_hash") == research_content_hash(research_artifact, contract)


def load_contract(root: Path) -> dict[str, Any]:
    return json.loads((Path(root) / "System" / "SYS_19_EVIDENCE_DEPTH_DIMENSIONS.json").read_text(encoding="utf-8"))


def load_evidence_context(root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    root = Path(root)
    evidence_library = json.loads((root / "System" / "SYS_18_EVIDENCE_LIBRARY.json").read_text(encoding="utf-8"))
    with (root / "Evidence" / "evidence_sources.csv").open(encoding="utf-8", newline="") as handle:
        source_type_by_id = {row["source_id"]: row["source_type"] for row in csv.DictReader(handle)}
    return evidence_library, source_type_by_id
def validate_gate1_disposition(
    research_artifact: dict[str, Any],
    disposition: dict[str, Any],
    contract: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    if not isinstance(disposition, dict):
        return ["13_gate1_disposition.json must contain a JSON object."]

    expected_hash = research_content_hash(research_artifact, contract)
    if disposition.get("research_artifact_hash") != expected_hash:
        errors.append(
            "13_gate1_disposition.json is stale for the canonical Research artifact."
        )

    expected_canonicalization = contract["canonicalization"]["version"]
    if disposition.get("canonicalization_version") != expected_canonicalization:
        errors.append(
            "13_gate1_disposition.json canonicalization_version does not match the Research contract."
        )

    claim_dispositions = disposition.get("claim_dispositions")
    if not isinstance(claim_dispositions, list):
        errors.append("13_gate1_disposition.json claim_dispositions must be a list.")
        return errors

    research_claims = research_artifact.get("claims")
    if not isinstance(research_claims, list):
        return errors

    research_claim_ids: list[str] = []
    for claim in research_claims:
        if isinstance(claim, dict) and _nonempty(claim.get("claim_id")):
            research_claim_ids.append(str(claim["claim_id"]))

    seen: set[str] = set()
    for item in claim_dispositions:
        if not isinstance(item, dict):
            errors.append("Each Gate-1 claim disposition must be an object.")
            continue

        claim_id = item.get("claim_id")
        if not _nonempty(claim_id):
            errors.append("Each Gate-1 claim disposition requires claim_id.")
            continue

        claim_id = str(claim_id)
        if claim_id in seen:
            errors.append(f"Duplicate Gate-1 disposition for claim_id {claim_id}.")
        seen.add(claim_id)

        if claim_id not in research_claim_ids:
            errors.append(
                f"Gate-1 disposition references unknown claim_id {claim_id}."
            )

        disposition_value = item.get("disposition")
        if disposition_value not in {"approved", "bounded", "rejected"}:
            errors.append(
                f"Gate-1 claim {claim_id} has invalid disposition {disposition_value!r}."
            )

        if disposition_value == "bounded":
            bounded_wording = item.get("bounded_wording")
            boundary = item.get("boundary")
            if not _nonempty(bounded_wording) and not _nonempty(boundary):
                errors.append(
                    f"Bounded Gate-1 claim {claim_id} requires bounded wording or boundary."
                )

        if not _nonempty(item.get("medical_notes")):
            errors.append(
                f"Gate-1 claim {claim_id} requires concise medical notes."
            )

    missing = [claim_id for claim_id in research_claim_ids if claim_id not in seen]
    if missing:
        errors.append(
            "Gate-1 disposition is missing Research claim IDs: "
            + ", ".join(missing)
        )

    return errors

def research_gate1_readiness(project: Path, root: Path) -> tuple[str, list[str]]:
    project = Path(project)
    required = (
        "02_research_sheet.md",
        "02_research_claims.json",
        "13_fact_check_log.md",
        "13_gate1_disposition.json",
    )
    missing = [name for name in required if not (project / name).is_file()]
    if missing:
        return "FAIL", [f"{name} is missing." for name in missing]

    try:
        research_artifact = json.loads(
            (project / "02_research_claims.json").read_text(encoding="utf-8")
        )
        disposition = json.loads(
            (project / "13_gate1_disposition.json").read_text(encoding="utf-8")
        )
        contract = load_contract(root)
        evidence_library, source_type_by_id = load_evidence_context(root)
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, csv.Error) as exc:
        return "FAIL", [f"Research/Gate-1 structured artifact could not be loaded: {exc}"]

    status, errors = validate_research_artifact(
        research_artifact,
        contract,
        evidence_library,
        source_type_by_id,
    )

    if status == HUMAN_DECISION_REQUIRED:
        return status, errors

    if status != "PASS":
        return "FAIL", errors

    gate1_errors = validate_gate1_disposition(
        research_artifact,
        disposition,
        contract,
    )
    if gate1_errors:
        return "FAIL", gate1_errors

    fact_check_log = (project / "13_fact_check_log.md").read_text(
        encoding="utf-8"
    ).strip()
    if not fact_check_log:
        return "FAIL", ["13_fact_check_log.md is empty."]

    return "PASS", []

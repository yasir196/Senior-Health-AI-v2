from __future__ import annotations

import hashlib
import json
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
    volatile = set(canon.get("volatile_fields", []))
    set_like = set(canon.get("set_like_arrays", []))
    semantic = {k: v for k, v in artifact.items() if k not in volatile}
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


def validate_research_artifact(artifact: dict[str, Any], contract: dict[str, Any]) -> tuple[str, list[str]]:
    errors: list[str] = []
    if artifact.get("dimensions_contract_version") != contract.get("version"):
        errors.append("dimensions_contract_version does not match the loaded contract")
    if artifact.get("canonicalization_version") != contract.get("canonicalization", {}).get("version"):
        errors.append("canonicalization_version does not match the loaded contract")

    tags = artifact.get("applicable_topic_tags") or []
    dims = {d.get("dimension"): d for d in artifact.get("dimensions", []) if isinstance(d, dict)}
    missing = sorted(expected_dimensions(contract, tags) - set(dims))
    if missing:
        errors.append("missing required dimensions: " + ", ".join(missing))

    allowed_status = set(contract.get("dimension_status_values", []))
    propositions = {p.get("proposition_id"): p for p in artifact.get("propositions", []) if isinstance(p, dict)}
    for name, dim in dims.items():
        status = dim.get("status")
        if status not in allowed_status:
            errors.append(f"{name}: invalid dimension status")
            continue
        linked = dim.get("proposition_ids") or []
        if status in {"supported", "partially_supported"}:
            if not linked or any(pid not in propositions for pid in linked):
                errors.append(f"{name}: supported status requires mapped propositions")
            if status == "partially_supported" and not str(dim.get("support_boundary") or "").strip():
                errors.append(f"{name}: partially_supported requires support_boundary")
        elif status == "no_evidence_found" and not str(dim.get("search_note") or "").strip():
            errors.append(f"{name}: no_evidence_found requires search_note")
        elif status == "not_applicable" and not str(dim.get("rationale") or "").strip():
            errors.append(f"{name}: not_applicable requires rationale")

    core = dims.get("core_proposition", {})
    if core and core.get("status") not in {"supported", "partially_supported"}:
        return HUMAN_DECISION_REQUIRED, [CORE_INSUFFICIENT]

    for pid, prop in propositions.items():
        evidence_ids = prop.get("evidence_source_ids") or []
        if not evidence_ids:
            errors.append(f"{pid}: material proposition requires evidence_source_ids")
        if prop.get("counterevidence_searched") is not True:
            errors.append(f"{pid}: counterevidence_searched must be true")
        if "counterevidence_found" not in prop:
            errors.append(f"{pid}: counterevidence_found must be recorded")
        if not str(prop.get("resulting_qualification") or "").strip():
            errors.append(f"{pid}: resulting_qualification is required")
        if not str(prop.get("saturation_note") or "").strip():
            errors.append(f"{pid}: saturation_note is required")

    claims = artifact.get("claims") or []
    for claim in claims:
        if not isinstance(claim, dict):
            errors.append("claim entry must be an object")
            continue
        if claim.get("population_metadata_status") == "metadata_incomplete" and claim.get("usable_for_production", True):
            errors.append(f"{claim.get('claim_id','claim')}: incomplete population metadata cannot be production-usable")

    expected_hash = research_content_hash(artifact, contract)
    recorded = artifact.get("research_content_hash")
    if recorded and recorded != expected_hash:
        errors.append("research_content_hash does not match canonical content")
    return ("FAIL", errors) if errors else ("PASS", [])


def gate1_is_current(research_artifact: dict[str, Any], disposition: dict[str, Any], contract: dict[str, Any]) -> bool:
    return disposition.get("research_artifact_hash") == research_content_hash(research_artifact, contract)


def load_contract(root: Path) -> dict[str, Any]:
    return json.loads((Path(root) / "System" / "SYS_19_EVIDENCE_DEPTH_DIMENSIONS.json").read_text(encoding="utf-8"))

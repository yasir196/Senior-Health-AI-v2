from __future__ import annotations

from typing import Any


def _norm(text: Any) -> str:
    return " ".join(str(text or "").upper().split())


def evaluate_rendered_image_qa(expected: dict[str, Any], observed: dict[str, Any], *, geometry_tolerance_pct: float = 8.0, angle_tolerance_deg: float = 1.0) -> dict[str, Any]:
    """Phase-2 deterministic comparison of pixel observations against Phase-1 contract."""
    findings: list[str] = []
    expected_bands=[x for x in (expected.get("text_bands") or []) if x.get("text")]
    observed_bands=observed.get("text_bands") or []

    exp_text=[_norm(x.get("text")) for x in expected_bands]
    obs_text=[_norm(x.get("text")) for x in observed_bands]
    if exp_text != obs_text:
        findings.append(f"visible text mismatch: expected {exp_text}, observed {obs_text}")

    if len(observed_bands) != len(expected_bands):
        findings.append(f"visible text band count {len(observed_bands)} != expected non-empty bands {len(expected_bands)}")

    for i,(exp,obs) in enumerate(zip(expected_bands,observed_bands),1):
        for key in ("x_pct","y_pct","w_pct","h_pct"):
            if abs(float(obs.get(key) or 0)-float(exp.get(key) or 0)) > geometry_tolerance_pct:
                findings.append(f"text band {i} {key} outside tolerance")
        if abs(float(obs.get("rotation_deg") or 0)) > angle_tolerance_deg:
            findings.append(f"text band {i} rotation exceeds {angle_tolerance_deg} deg")
        if abs(float(obs.get("slant_deg") or 0)) > angle_tolerance_deg:
            findings.append(f"text band {i} glyph slant exceeds {angle_tolerance_deg} deg")

    budget=expected.get("complexity_budget") or {}
    people=int(observed.get("people_count") or 0)
    objects=int(observed.get("informational_object_count") or 0)
    attention=int(observed.get("attention_device_count") or 0)
    if people > int(budget.get("max_people") or 0):
        findings.append(f"pixel people count {people} exceeds budget {int(budget.get('max_people') or 0)}")
    if objects > int(budget.get("max_informational_objects") or 0):
        findings.append(f"pixel informational object count {objects} exceeds budget {int(budget.get('max_informational_objects') or 0)}")
    if attention > int(budget.get("max_attention_devices") or 0):
        findings.append(f"pixel attention device count {attention} exceeds budget {int(budget.get('max_attention_devices') or 0)}")

    if observed.get("extra_visible_text"):
        findings.append("extra visible text detected")
    if observed.get("extra_informational_objects"):
        findings.append("extra informational objects detected")
    if observed.get("timestamp_safe_zone_clear") is False:
        findings.append("bottom-right timestamp safe zone is not clear")

    expected_targets=[x for x in (expected.get("visual_placements") or []) if x.get("is_primary_target")]
    if len(expected_targets)==1:
        target_role=str(expected_targets[0].get("role_id") or "")
        observed_target=str(observed.get("primary_target_role_id") or "")
        if observed_target != target_role:
            findings.append(f"primary target mismatch: expected {target_role}, observed {observed_target or 'none'}")
        attention_target=str(observed.get("attention_target_role_id") or "")
        if attention and attention_target != target_role:
            findings.append(f"attention mapping mismatch: expected {target_role}, observed {attention_target or 'none'}")

    return {"verdict":"PASS" if not findings else "FAIL","findings":findings,"observed":observed}

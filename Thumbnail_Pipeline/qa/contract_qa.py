from __future__ import annotations

from typing import Any


TEXT_SLOT_ORDER = ("top_banner", "primary_headline", "boxed_keyword", "bottom_callout")


def build_render_structure(winner_metadata: dict[str, Any], adaptation: dict[str, Any], selected_text: str | None) -> dict[str, Any]:
    """Flatten winner topology + adapted semantics into measurable pre-render fields."""
    structural = (winner_metadata or {}).get("structural_contract") or {}
    bands = sorted(
        [dict(x) for x in (structural.get("bands") or []) if isinstance(x, dict)],
        key=lambda x: int(x.get("reading_order") or 0),
    )
    visible = [(k, str(adaptation.get(k) or "").strip()) for k in TEXT_SLOT_ORDER if str(adaptation.get(k) or "").strip()]
    if bands and len(visible) > len(bands):
        raise ValueError("Adapted copy exceeds winner text-band capacity.")

    rendered_bands=[]
    for idx, band in enumerate(bands):
        item=dict(band)
        item["rotation_deg"]=0.0
        item["slant_deg"]=0.0
        item["wrap_policy"]="inside_band_only"
        if idx < len(visible):
            item["semantic_slot"], item["text"] = visible[idx]
        else:
            item["semantic_slot"], item["text"] = None, None
        rendered_bands.append(item)

    roles=[dict(x) for x in (structural.get("roles") or []) if isinstance(x,dict)]
    return {
        "text_bands": rendered_bands,
        "visual_roles": roles,
        "complexity_budget": dict(structural.get("complexity_budget") or {}),
        "selected_text": str(selected_text or "").strip(),
    }


def evaluate_contract_qa(render_structure: dict[str, Any]) -> dict[str, Any]:
    """Deterministic Phase-1 invariants. No LLM judgment."""
    findings=[]
    bands=render_structure.get("text_bands") or []
    budget=render_structure.get("complexity_budget") or {}
    selected=str(render_structure.get("selected_text") or "")

    expected=int(budget.get("text_band_count") or len(bands))
    if len(bands) != expected:
        findings.append(f"text_band_count {len(bands)} != winner budget {expected}")

    ids=[str(x.get("band_id") or "") for x in bands]
    if any(not x for x in ids) or len(ids)!=len(set(ids)):
        findings.append("band_id values must be non-empty and unique")

    slots=[str(x.get("semantic_slot") or "") for x in bands if x.get("semantic_slot")]
    if len(slots)!=len(set(slots)):
        findings.append("semantic slot maps to more than one band")

    for band in bands:
        if float(band.get("rotation_deg") or 0) != 0.0:
            findings.append(f"{band.get('band_id')}: rotation_deg must equal 0")
        if float(band.get("slant_deg") or 0) != 0.0:
            findings.append(f"{band.get('band_id')}: slant_deg must equal 0")
        if band.get("wrap_policy") != "inside_band_only":
            findings.append(f"{band.get('band_id')}: wrap_policy must be inside_band_only")

    if selected:
        exact=sum(1 for x in bands if str(x.get("text") or "") == selected)
        if exact != 1:
            findings.append(f"immutable selected copy must appear exactly once; found {exact}")

    roles=render_structure.get("visual_roles") or []
    people=sum(1 for x in roles if str(x.get("role_type") or "").casefold() in {"presenter","person","human","portrait"})
    max_people=int(budget.get("max_people") or 0)
    if people > max_people:
        findings.append(f"people roles {people} exceed winner budget {max_people}")

    targets=[x for x in roles if str(x.get("role_type") or "").casefold()=="target"]
    target_ids={str(x.get("role_id") or "") for x in targets}
    bound=[str(x.get("attention_target_role_id") or "") for x in roles if x.get("attention_target_role_id")]
    if bound and (len(set(bound)) != 1 or not set(bound).issubset(target_ids)):
        findings.append("attention relationships must resolve to one winner target role")

    return {"verdict":"PASS" if not findings else "FAIL","findings":findings,"render_structure":render_structure}

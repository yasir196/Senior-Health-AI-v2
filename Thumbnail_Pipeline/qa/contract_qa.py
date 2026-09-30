from __future__ import annotations

from typing import Any


TEXT_SLOT_ORDER = ("top_banner", "primary_headline", "boxed_keyword", "bottom_callout")
SPLIT_MARKER = " | "
PEOPLE_ROLE_TYPES = {"presenter", "person", "human", "portrait"}
NON_INFORMATIONAL_ROLE_TYPES = PEOPLE_ROLE_TYPES | {"support/chair", "chair", "support", "environment", "background"}
ATTENTION_ROLE_TYPES = {"attention_device", "arrow", "circle", "highlight"}


def _segments(slot: str, text: str, selected: str) -> list[tuple[str, str, int | None]]:
    # Immutable selected copy is one semantic unit: wrapping is allowed inside one
    # winner band, but it may never be split into extra panels.
    if selected and text == selected:
        return [(slot, text, None)]
    parts=[x.strip() for x in text.split(SPLIT_MARKER)]
    if len(parts) > 1 and all(parts):
        return [(slot, part, i) for i,part in enumerate(parts)]
    return [(slot, text, None)]


def build_render_structure(winner_metadata: dict[str, Any], adaptation: dict[str, Any], selected_text: str | None) -> dict[str, Any]:
    """Flatten winner topology + adapted semantics into measurable pre-render fields."""
    structural=(winner_metadata or {}).get("structural_contract") or {}
    bands=sorted(
        [dict(x) for x in (structural.get("bands") or []) if isinstance(x,dict)],
        key=lambda x:int(x.get("reading_order") or 0),
    )
    selected=str(selected_text or "").strip()
    assignments=[]
    for slot in TEXT_SLOT_ORDER:
        value=str(adaptation.get(slot) or "").strip()
        if value:
            assignments.extend(_segments(slot,value,selected))
    if bands and len(assignments) > len(bands):
        raise ValueError("Adapted copy exceeds winner text-band capacity.")

    rendered_bands=[]
    for idx,band in enumerate(bands):
        item=dict(band)
        # Render requirement is deliberately upright even if the historical winner
        # measurement was slanted. Source measurement remains in winner_metadata.json.
        item["rotation_deg"]=0.0
        item["slant_deg"]=0.0
        item["wrap_policy"]="inside_band_only"
        if idx < len(assignments):
            slot,text,segment_index=assignments[idx]
            item["semantic_slot"]=slot
            item["text"]=text
            item["segment_index"]=segment_index
        else:
            item["semantic_slot"]=None
            item["text"]=None
            item["segment_index"]=None
        rendered_bands.append(item)

    winner_roles=[dict(x) for x in (structural.get("roles") or []) if isinstance(x,dict)]
    visual_placements=[dict(x) for x in (adaptation.get("visual_placements") or []) if isinstance(x,dict)]
    return {
        "text_bands":rendered_bands,
        "winner_visual_roles":winner_roles,
        "visual_placements":visual_placements,
        "complexity_budget":dict(structural.get("complexity_budget") or {}),
        "selected_text":selected,
    }


def evaluate_contract_qa(render_structure: dict[str, Any]) -> dict[str, Any]:
    """Deterministic Phase-1 invariants. No LLM judgment or prose object counting."""
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

    # One slot may occupy multiple bands only through explicit split segments, which
    # must be consecutive and zero-based. Otherwise slot->band is bijective.
    by_slot={}
    for i,band in enumerate(bands):
        slot=band.get("semantic_slot")
        if slot:
            by_slot.setdefault(str(slot),[]).append((i,band.get("segment_index")))
    for slot,items in by_slot.items():
        if len(items)<=1:
            continue
        indexes=[x[0] for x in items]
        segments=[x[1] for x in items]
        if indexes != list(range(indexes[0],indexes[0]+len(indexes))) or segments != list(range(len(items))):
            findings.append(f"{slot}: multi-band mapping requires explicit consecutive split segments")

    for band in bands:
        if float(band.get("rotation_deg") or 0) != 0.0:
            findings.append(f"{band.get('band_id')}: rotation_deg must equal 0")
        if float(band.get("slant_deg") or 0) != 0.0:
            findings.append(f"{band.get('band_id')}: slant_deg must equal 0")
        if band.get("wrap_policy")!="inside_band_only":
            findings.append(f"{band.get('band_id')}: wrap_policy must be inside_band_only")

    if selected:
        exact=sum(1 for x in bands if str(x.get("text") or "") == selected)
        if exact != 1:
            findings.append(f"immutable selected copy must appear exactly once as one unsplit band unit; found {exact}")

    winner_roles=render_structure.get("winner_visual_roles") or []
    winner_role_ids={str(x.get("role_id") or "") for x in winner_roles if x.get("role_id")}
    winner_role_type={str(x.get("role_id") or ""):str(x.get("role_type") or "").casefold() for x in winner_roles}
    placements=render_structure.get("visual_placements") or []

    placement_ids=[str(x.get("placement_id") or "") for x in placements]
    if any(not x for x in placement_ids) or len(placement_ids)!=len(set(placement_ids)):
        findings.append("visual placement_id values must be non-empty and unique")

    for placement in placements:
        role_id=str(placement.get("role_id") or "")
        if role_id not in winner_role_ids:
            findings.append(f"{placement.get('placement_id')}: visual placement has no winner role binding")

    people=sum(1 for x in placements if str(x.get("kind") or "").casefold()=="person")
    max_people=int(budget.get("max_people") or 0)
    if people > max_people:
        findings.append(f"people placements {people} exceed winner budget {max_people}")

    informational=sum(1 for x in placements if str(x.get("kind") or "").casefold()=="informational_object")
    max_objects=int(budget.get("max_informational_objects") or 0)
    if informational > max_objects:
        findings.append(f"informational object placements {informational} exceed winner budget {max_objects}")

    attention=sum(1 for x in placements if str(x.get("kind") or "").casefold()=="attention_device")
    max_attention=int(budget.get("max_attention_devices") or 0)
    if attention > max_attention:
        findings.append(f"attention device placements {attention} exceed winner budget {max_attention}")

    # Environment/support/chair are explicitly non-informational and do not consume
    # the object budget. Presenter/person consumes max_people, not object budget.
    for placement in placements:
        role_id=str(placement.get("role_id") or "")
        kind=str(placement.get("kind") or "").casefold()
        role_type=winner_role_type.get(role_id,"")
        if kind=="person" and role_type not in PEOPLE_ROLE_TYPES:
            findings.append(f"{placement.get('placement_id')}: person must bind to a winner people role")
        if kind=="attention_device" and role_type not in ATTENTION_ROLE_TYPES:
            findings.append(f"{placement.get('placement_id')}: attention device must bind to a winner attention role")
        if kind=="informational_object" and role_type in NON_INFORMATIONAL_ROLE_TYPES:
            findings.append(f"{placement.get('placement_id')}: informational object cannot bind to {role_type} role")

    target_placements=[x for x in placements if str(x.get("kind") or "").casefold()=="informational_object" and bool(x.get("is_primary_target"))]
    if len(target_placements)!=1:
        findings.append(f"exactly one primary informational target is required; found {len(target_placements)}")
    target_role_id=str(target_placements[0].get("role_id") or "") if len(target_placements)==1 else ""
    bound=[str(x.get("attention_target_role_id") or "") for x in placements if str(x.get("kind") or "").casefold()=="attention_device"]
    if bound and (len(set(bound))!=1 or set(bound)!={target_role_id}):
        findings.append("adapted attention devices must resolve to the one primary target role")

    return {"verdict":"PASS" if not findings else "FAIL","findings":findings,"render_structure":render_structure}

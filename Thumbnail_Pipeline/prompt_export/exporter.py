from __future__ import annotations
from typing import Any
from Thumbnail_Pipeline.generation import build_generation_handoff

def export_final_thumbnail_prompt(composition_spec: dict[str, Any], gate: dict[str, Any], *, selected_text: str | None = None, winner_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Export the reviewed thumbnail prompt contract only; never render or publish."""
    handoff = build_generation_handoff(composition_spec, gate, selected_text=selected_text)
    contract = handoff["render_contract"]
    missing = [k for k in ("layout","subject_placement","text_placement","safe_zone") if contract.get(k) in (None,"")]
    if missing:
        raise ValueError(f"Final prompt requires resolved composition fields: {missing}")
    lines = [
        "Create a 16:9 YouTube thumbnail (1280x720).",
        f"VIDEO TITLE (context only; do not rewrite): {handoff['immutable_title']}",
        f"LAYOUT: {contract['layout']}",
        f"SUBJECT PLACEMENT: {contract['subject_placement']}",
        f"TEXT PLACEMENT: {contract['text_placement']}",
        f"SAFE ZONE: {contract['safe_zone']}",
        "FONT RULE: Use a bold block sans-serif font with perfectly upright, straight vertical letterforms and 0% slant. No italic, oblique, cursive, script, skewed, or slanted text.",
    ]
    signature=contract.get("structural_signature") or {}
    zone_labels=(("text_zone","TEXT ZONE"),("primary_visual_zone","PRIMARY VISUAL ZONE"),("presenter_zone","PRESENTER ZONE"),("secondary_visual_zone","SECONDARY VISUAL ZONE"))
    for key,label in zone_labels:
        value=signature.get(key)
        if value and value not in ("none","unknown"):
            lines.append(f"{label}: {value}")
    if contract.get("visual_strategy")=="object_led_no_presenter":
        lines.append("VISUAL STRATEGY: Object-led composition matching the DB winner. Do not use a presenter, portrait, or human face as the primary visual.")
    elif contract.get("visual_strategy")=="presenter_led":
        lines.append("VISUAL STRATEGY: Presenter-led composition matching the DB winner.")
    if contract.get("thumbnail_text"):
        lines.append(f"THUMBNAIL TEXT (exact): {contract['thumbnail_text']}")
    metadata=winner_metadata if isinstance(winner_metadata,dict) else {}
    if metadata:
        geometry=metadata.get("layout_geometry") or {}
        colors=metadata.get("color_system") or {}
        attention=metadata.get("attention_devices") or {}
        reusable=metadata.get("reusable_composition_contract") or {}
        roles=reusable.get("roles_and_placeholders") or {}
        swap_rules=reusable.get("swap_rules") or {}
        topic_split=reusable.get("topic_specific_vs_reusable") or {}
        lines.append("WINNER METADATA CONTRACT: Use the fresh selected-winner pixel analysis below as the single source of truth for composition. Preserve reusable structure/style; replace topic-specific words and imagery for the current video.")
        if geometry:
            lines.append("WINNER LAYOUT GEOMETRY: "+str(geometry))
        if colors:
            lines.append("WINNER COLOR SYSTEM: "+str(colors))
        if roles:
            lines.append("REUSABLE COMPOSITION ROLES: "+str(roles))
        if attention:
            lines.append("ATTENTION DEVICES: "+str(attention))
        if swap_rules:
            lines.append("TOPIC SUBSTITUTION RULES: "+str(swap_rules))
        if topic_split:
            lines.append("TOPIC-SPECIFIC VS REUSABLE: "+str(topic_split))
        lines.append("CURRENT-TOPIC ADAPTATION: Derive topic-specific subject/object wording only from the immutable current video title and selected thumbnail text. Do not import peanut butter or any other historical winner topic content. Do not combine people/objects from multiple YouTube reference thumbnails.")
    else:
        subjects=[str(x).strip() for x in (contract.get("visual_subject_examples") or []) if str(x).strip()]
        if subjects:
            lines.append("CURRENT-TOPIC VISUAL EVIDENCE: " + " | ".join(subjects[:5]))
            lines.append("VISUAL SUBJECT DIRECTION: Use only a subject visibly supported by the current-topic YouTube evidence above; do not copy unrelated historical cluster objects.")
    lines += [
        "Follow the reviewed composition exactly.",
        "Do not add extra text, claims, badges, labels, people, or visual elements not specified by the reviewed contract.",
    ]
    return {
        "schema_version":"0.19.0",
        "immutable_title":handoff["immutable_title"],
        "category":handoff.get("category"),
        "final_prompt":"\n".join(lines),
        "prompt_contract":contract,
        "provenance":handoff.get("provenance") or {},
        "image_generation_executed":False,
        "youtube_upload_executed":False,
        "v2_write_performed":False,
    }

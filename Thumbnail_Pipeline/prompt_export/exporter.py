from __future__ import annotations
from typing import Any
from Thumbnail_Pipeline.generation import build_generation_handoff

def _derived_reusable_roles(metadata: dict[str, Any]) -> dict[str, Any]:
    """Derive stable composition slots when vision omits nested reusable roles."""
    text=metadata.get("text") or {}
    zones=text.get("text_zones") or []
    zone_ids={str(z.get("id") or "").strip():z for z in zones if isinstance(z,dict)}
    primary=metadata.get("primary_visual") or {}
    secondary=metadata.get("secondary_visual") or {}
    attention=metadata.get("attention_devices") or {}
    roles: dict[str, Any]={}
    def add_text(role: str, zone_id: str, purpose: str) -> None:
        z=zone_ids.get(zone_id)
        if z:
            roles[role]={"role":purpose,"geometry":z.get("bounds_normalized"),"formatting":z.get("font_style"),"color":z.get("color"),"background_color":z.get("background_color")}
    add_text("top_banner_text","top_banner","Audience/context banner; substitute current-topic copy while preserving banner geometry/style")
    headline=[z for z in zones if isinstance(z,dict) and str(z.get("id") or "").startswith("headline_line")]
    if headline:
        roles["headline_lines"]={"role":"Primary current-topic hook","line_count":len(headline),"geometry":[z.get("bounds_normalized") for z in headline],"formatting":[z.get("font_style") for z in headline],"colors":[z.get("color") for z in headline]}
    add_text("boxed_keyword","boxed_keyword","Current-topic keyword/subject emphasis box")
    add_text("bottom_line","bottom_line","Short current-topic context/callout")
    if primary:
        roles["primary_subject_image"]={"role":"Current-topic primary photographic/object subject","geometry":primary.get("bounds_normalized"),"treatment":primary.get("visual_treatment"),"human_present":primary.get("human_present")}
    if secondary:
        roles["secondary_detail"]={"role":"Current-topic secondary detail related to the primary subject","geometry":secondary.get("spoon_bounds_normalized") or secondary.get("bounds_normalized"),"highlight":secondary.get("highlight")}
    if attention:
        roles["attention_devices"]={"role":"Preserve winner attention-device types and relative placement; retarget them to the substituted current-topic detail","winner_devices":attention.get("present") or attention.get("devices_present")}
    return roles

def export_final_thumbnail_prompt(composition_spec: dict[str, Any], gate: dict[str, Any], *, selected_text: str | None = None, winner_metadata: dict[str, Any] | None = None, topic_adaptation: dict[str, Any] | None = None, render_structure: dict[str, Any] | None = None) -> dict[str, Any]:
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
        "FONT RULE — HARD OVERRIDE: Every visible letter must use a bold condensed/block sans-serif with perfectly upright vertical stems and EXACTLY 0° slant. REGULAR/UPRIGHT ROMAN ONLY. Italic, oblique, faux-italic, cursive, script, skew, shear, perspective-slanted lettering, rotated words, and angled text boxes are forbidden. Do not imitate any slant seen in a reference image. If the chosen font has an italic/oblique variant, use its upright regular/bold variant only.",
        "TEXT ORIENTATION LOCK: Keep every text baseline horizontal (0° rotation) and every text band/rectangle axis-aligned to the canvas. No tilted cards, diagonal banners, trapezoid/perspective text panels, or leaning glyphs. Text may wrap inside its assigned band, but wrapping must not change the upright 0° typography.",
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
        roles=reusable.get("roles_and_placeholders") or _derived_reusable_roles(metadata)
        swap_rules=reusable.get("swap_rules") or {
            "text_substitution":"Replace historical winner words with current-video wording while preserving each slot's geometry, hierarchy, casing role, and styling.",
            "image_substitution":"Replace historical winner objects with one coherent current-topic primary subject plus one related secondary detail; preserve winner placement and crop.",
            "attention_substitution":"Preserve winner arrow/circle/highlight devices and point them only at the substituted current-topic secondary detail."
        }
        topic_split=reusable.get("topic_specific_vs_reusable") or {
            "topic_specific":["all historical visible words","historical primary object/content","historical secondary detail/content"],
            "reusable_structure":["banner/headline/keyword/callout roles","positions and approximate sizes","color-role system","typography hierarchy","primary/secondary visual relationship","arrow/circle/highlight pattern"]
        }
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
        structure=render_structure if isinstance(render_structure,dict) else {}
        if structure:
            lines.append("RENDER STRUCTURE — HARD, MEASURABLE CONTRACT:")
            lines.append("TEXT BANDS JSON: "+str(structure.get("text_bands") or []))
            lines.append("WINNER VISUAL ROLES JSON: "+str(structure.get("winner_visual_roles") or []))
            lines.append("ADAPTED VISUAL PLACEMENTS JSON: "+str(structure.get("visual_placements") or []))
            lines.append("COMPLEXITY BUDGET: "+str(structure.get("complexity_budget") or {}))
            lines.append("RENDER INVARIANTS: Text band count is fixed. Each semantic slot stays inside its assigned band. Wrapping may occur only inside that same rectangle and must never create a new panel. Every band is axis-aligned with rotation_deg=0 and slant_deg=0. ADAPTED VISUAL PLACEMENTS JSON is the SINGLE EXECUTABLE SOURCE OF TRUTH for visible people, objects, supports, environment, and attention devices. Do not render any prop or visual object mentioned elsewhere unless it has its own approved adapted placement. Environment is atmosphere only; support is structure only. Do not create extra informational objects or people beyond the winner-derived complexity budget. Empty optional roles are valid and preferable to clutter.")
        adaptation=topic_adaptation if isinstance(topic_adaptation,dict) else {}
        if adaptation:
            lines.append("CURRENT-TOPIC SLOT CONTRACT (use these exact semantic assignments):")
            for key,label in (("top_banner","TOP BANNER"),("primary_headline","PRIMARY HEADLINE"),("boxed_keyword","BOXED KEYWORD"),("bottom_callout","BOTTOM CALLOUT")):
                value=adaptation.get(key)
                if value not in (None,""):
                    lines.append(f"{label}: {value}")
            lines.append("SLOT RULE: Preserve winner metadata geometry/style for text slots. Historical winner words/objects are reference semantics only. For visuals, ignore free-prose primary_visual/secondary_detail/attention_target fields at render time; render ONLY ADAPTED VISUAL PLACEMENTS JSON.")
        else:
            lines.append("CURRENT-TOPIC ADAPTATION: Derive topic-specific subject/object wording only from the immutable current video title and selected thumbnail text. Do not import historical winner topic content. Do not combine people/objects from multiple YouTube reference thumbnails.")
    else:
        subjects=[str(x).strip() for x in (contract.get("visual_subject_examples") or []) if str(x).strip()]
        if subjects:
            lines.append("CURRENT-TOPIC VISUAL EVIDENCE: " + " | ".join(subjects[:5]))
            lines.append("VISUAL SUBJECT DIRECTION: Use only a subject visibly supported by the current-topic YouTube evidence above; do not copy unrelated historical cluster objects.")
    lines += [
        "Follow the reviewed composition exactly.",
        "FINAL TYPOGRAPHY CHECK BEFORE RENDER: reject and regenerate internally if ANY glyph, word, baseline, or text panel appears italic, oblique, leaning, skewed, sheared, rotated, or perspective-slanted. All visible copy must remain perfectly upright at 0°.",
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

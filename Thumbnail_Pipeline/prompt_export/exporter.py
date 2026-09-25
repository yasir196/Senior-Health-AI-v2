from __future__ import annotations
from typing import Any
from Thumbnail_Pipeline.generation import build_generation_handoff

def export_final_thumbnail_prompt(composition_spec: dict[str, Any], gate: dict[str, Any], *, selected_text: str | None = None) -> dict[str, Any]:
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
    ]
    if contract.get("thumbnail_text"):
        lines.append(f"THUMBNAIL TEXT (exact): {contract['thumbnail_text']}")
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

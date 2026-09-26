from __future__ import annotations

from typing import Any


def build_generation_handoff(
    composition_spec: dict[str, Any],
    gate: dict[str, Any],
    *,
    selected_text: str | None = None,
) -> dict[str, Any]:
    """Build a renderer-neutral handoff. No external generator is called here."""
    if not gate.get("approved"):
        raise ValueError("Generation gate is not approved.")
    if gate.get("immutable_title") != composition_spec.get("immutable_title"):
        raise ValueError("Immutable title mismatch between composition and gate.")

    composition = composition_spec.get("composition") or {}
    candidates = [str(x) for x in (composition.get("thumbnail_text_candidates") or []) if str(x)]
    if selected_text is not None and selected_text not in candidates:
        raise ValueError("Selected thumbnail text must come from reviewed candidates.")

    return {
        "schema_version": "0.5.0",
        "immutable_title": composition_spec.get("immutable_title") or "",
        "category": composition_spec.get("category"),
        "render_contract": {
            "layout": composition.get("layout"),
            "subject_placement": composition.get("subject_placement"),
            "text_placement": composition.get("text_placement"),
            "safe_zone": composition.get("safe_zone"),
            "thumbnail_text": selected_text,
            "visual_subject_examples": composition.get("visual_subject_examples") or [],
        },
        "provenance": composition_spec.get("provenance") or {},
        "gate": {
            "approved": True,
            "schema_version": gate.get("schema_version"),
        },
        "renderer_status": "not_invoked",
    }

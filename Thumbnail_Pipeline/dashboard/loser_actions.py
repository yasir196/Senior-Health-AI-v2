from __future__ import annotations
from typing import Any
from Thumbnail_Pipeline.generation.contracts import GenerationRequest, final_generation_prompt


def loser_repair_card(*, audit_id: int, title: str, original_text: str, why: list[dict[str, Any]], suggestion: dict[str, Any], proposed_text: str, editable_prompt: str) -> dict[str, Any]:
    request = GenerationRequest(
        audit_id=audit_id,
        title=title,
        proposed_thumbnail_text=proposed_text,
        prompt=editable_prompt,
    )
    return {
        "audit_id": audit_id,
        "title": title,
        "original_thumbnail_text_full": original_text,
        "why_lower_ctr": why,
        "suggestion_for_loser": suggestion,
        "proposed_thumbnail_text": proposed_text,
        "editable_image_prompt": editable_prompt,
        "generate_now": {
            "enabled": True,
            "button_label": "Generate Now",
            "request_preview": request.payload(),
            "final_prompt_preview": final_generation_prompt(request),
            "status": "provider_required",
        },
    }

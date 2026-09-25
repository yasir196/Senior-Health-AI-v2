from __future__ import annotations
from typing import Any, Protocol

class ImageGenerationBackend(Protocol):
    def generate(self, request: dict[str, Any]) -> dict[str, Any]: ...

def build_provider_request(handoff: dict[str, Any]) -> dict[str, Any]:
    """Translate the internal handoff to a backend-neutral request."""
    if handoff.get("renderer_status") != "not_invoked":
        raise ValueError("Provider request requires a fresh renderer handoff.")
    contract = handoff.get("render_contract") or {}
    required = ("layout","subject_placement","text_placement","safe_zone")
    missing = [k for k in required if contract.get(k) in (None,"")]
    if missing:
        raise ValueError(f"Provider request has unresolved render fields: {missing}")
    return {
        "schema_version":"0.11.0",
        "immutable_title":handoff.get("immutable_title") or "",
        "category":handoff.get("category"),
        "instructions":{
            "layout":contract["layout"],
            "subject_placement":contract["subject_placement"],
            "text_placement":contract["text_placement"],
            "safe_zone":contract["safe_zone"],
            "thumbnail_text":contract.get("thumbnail_text"),
        },
        "provenance":handoff.get("provenance") or {},
    }

class ContractRendererProvider:
    """Explicit adapter around an injected image backend; no backend is bundled."""
    def __init__(self, backend: ImageGenerationBackend):
        self.backend = backend

    def render(self, handoff: dict[str, Any]) -> dict[str, Any]:
        request = build_provider_request(handoff)
        result = self.backend.generate(request)
        if not isinstance(result, dict):
            raise ValueError("Image backend result must be a mapping.")
        return result

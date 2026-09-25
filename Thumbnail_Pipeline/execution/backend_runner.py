from __future__ import annotations
from typing import Any
from Thumbnail_Pipeline.providers import ContractRendererProvider
from Thumbnail_Pipeline.runner import run_render_stage

def run_with_backend(
    composition_spec: dict[str, Any],
    gate: dict[str, Any],
    *,
    backend: Any,
    selected_text: str | None = None,
    execute: bool = False,
    observed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind an injected image backend to the safe runner without adding a bundled API."""
    if backend is None:
        raise ValueError("An image-generation backend must be explicitly supplied.")
    provider = ContractRendererProvider(backend)
    result = run_render_stage(
        composition_spec,
        gate,
        selected_text=selected_text,
        provider=provider,
        execute=execute,
        observed=observed,
    )
    result["schema_version"] = "0.12.0"
    result["backend_bound"] = True
    result["backend_executed"] = bool(result.get("render", {}).get("renderer_invoked"))
    return result

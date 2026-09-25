from __future__ import annotations
from typing import Any
from Thumbnail_Pipeline.generation import build_generation_handoff
from Thumbnail_Pipeline.renderer import dispatch_renderer
from Thumbnail_Pipeline.orchestration import advance_rendered_asset

def run_render_stage(
    composition_spec: dict[str, Any],
    gate: dict[str, Any],
    *,
    selected_text: str | None = None,
    provider: Any = None,
    execute: bool = False,
    observed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the renderer boundary and, only after execution, downstream QA/finalization."""
    handoff = build_generation_handoff(composition_spec, gate, selected_text=selected_text)
    render = dispatch_renderer(handoff, provider=provider, execute=execute)
    result = {"schema_version":"0.10.0","handoff":handoff,"render":render,"downstream":None}
    if render.get("status") == "rendered":
        result["downstream"] = advance_rendered_asset(render, observed=observed)
    return result

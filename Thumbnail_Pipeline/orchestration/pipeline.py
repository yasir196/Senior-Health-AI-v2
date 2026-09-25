from __future__ import annotations

from typing import Any

from Thumbnail_Pipeline.qa import evaluate_post_render_qa
from Thumbnail_Pipeline.finalization import finalize_thumbnail_asset, build_publish_handoff


def advance_rendered_asset(
    render_response: dict[str, Any],
    *,
    observed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Advance a rendered asset through QA without bypassing human-review gates."""
    if render_response.get("status") != "rendered" or not render_response.get("renderer_invoked"):
        raise ValueError("Only an executed renderer response may enter post-render orchestration.")
    artifact = render_response.get("artifact")
    if not isinstance(artifact, dict):
        raise ValueError("Rendered response is missing its validated artifact.")

    qa = evaluate_post_render_qa(artifact, observed=observed)
    result = {
        "schema_version": "0.9.0",
        "stage": "post_render_qa",
        "artifact": artifact,
        "qa": qa,
        "final_record": None,
        "publish_handoff": None,
    }
    if qa.get("final_asset_accepted") is True:
        final_record = finalize_thumbnail_asset(artifact, qa)
        result["stage"] = "finalized"
        result["final_record"] = final_record
        result["publish_handoff"] = build_publish_handoff(final_record)
    return result

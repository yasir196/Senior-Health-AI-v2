from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
_OUTPUT_ROOT = PurePosixPath("Thumbnail_Pipeline/outputs")


def validate_render_result(result: dict[str, Any], handoff: dict[str, Any]) -> dict[str, Any]:
    """Normalize renderer output and enforce the isolated output contract."""
    if not isinstance(result, dict):
        raise ValueError("Renderer result must be a mapping.")

    path_text = str(result.get("output_path") or "").replace("\\", "/")
    if not path_text:
        raise ValueError("Renderer result must include output_path.")

    path = PurePosixPath(path_text)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Renderer output_path must stay inside Thumbnail_Pipeline/outputs/.")

    root_parts = _OUTPUT_ROOT.parts
    if path.parts[: len(root_parts)] != root_parts:
        raise ValueError("Renderer output_path must stay inside Thumbnail_Pipeline/outputs/.")
    if path.suffix.lower() not in _ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported thumbnail output extension.")

    width = int(result.get("width") or 0)
    height = int(result.get("height") or 0)
    if width <= 0 or height <= 0:
        raise ValueError("Renderer result must include positive width and height.")

    returned_title = result.get("immutable_title")
    expected_title = handoff.get("immutable_title") or ""
    if returned_title not in (None, expected_title):
        raise ValueError("Renderer result attempted to change immutable title.")

    return {
        "schema_version": "0.6.0",
        "asset": {
            "output_path": path.as_posix(),
            "width": width,
            "height": height,
            "mime_type": result.get("mime_type"),
            "asset_id": result.get("asset_id"),
        },
        "immutable_title": expected_title,
        "render_contract": handoff.get("render_contract") or {},
        "provenance": handoff.get("provenance") or {},
        "qa_status": "pending",
    }

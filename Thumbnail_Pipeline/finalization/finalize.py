from __future__ import annotations

from copy import deepcopy
from pathlib import PurePosixPath
from typing import Any

_OUTPUT_ROOT = PurePosixPath("Thumbnail_Pipeline/outputs")


def finalize_thumbnail_asset(artifact: dict[str, Any], qa_result: dict[str, Any]) -> dict[str, Any]:
    """Create an immutable finalization record only after Phase 7 acceptance."""
    if qa_result.get("final_asset_accepted") is not True or qa_result.get("status") != "passed":
        raise ValueError("Thumbnail cannot be finalized before post-render QA passes.")
    if (qa_result.get("immutable_title") or "") != (artifact.get("immutable_title") or ""):
        raise ValueError("Immutable title mismatch between artifact and QA result.")

    asset = artifact.get("asset") or {}
    path = PurePosixPath(str(asset.get("output_path") or "").replace("\\", "/"))
    if path.parts[: len(_OUTPUT_ROOT.parts)] != _OUTPUT_ROOT.parts or ".." in path.parts:
        raise ValueError("Final asset must remain inside Thumbnail_Pipeline/outputs/.")

    return {
        "schema_version": "0.8.0",
        "status": "final",
        "immutable_title": artifact.get("immutable_title") or "",
        "asset": deepcopy(asset),
        "render_contract": deepcopy(artifact.get("render_contract") or {}),
        "provenance": deepcopy(artifact.get("provenance") or {}),
        "qa": {
            "schema_version": qa_result.get("schema_version"),
            "status": "passed",
            "checks": deepcopy(qa_result.get("checks") or {}),
            "human_review": deepcopy(qa_result.get("human_review")) if qa_result.get("human_review") else None,
        },
        "publish_status": "not_published",
        "v2_write_performed": False,
    }


def build_publish_handoff(final_record: dict[str, Any]) -> dict[str, Any]:
    """Prepare a publish-neutral handoff. This does not upload or mutate V2."""
    if final_record.get("status") != "final":
        raise ValueError("Only finalized thumbnail assets may enter publish handoff.")
    return {
        "schema_version": "0.8.0",
        "immutable_title": final_record.get("immutable_title") or "",
        "asset": deepcopy(final_record.get("asset") or {}),
        "status": "ready_for_explicit_publish_action",
        "publish_executed": False,
        "v2_write_performed": False,
        "instruction": "No upload or V2 mutation is performed by this handoff.",
    }

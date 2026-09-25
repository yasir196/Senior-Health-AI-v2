from __future__ import annotations
import hashlib
import json
from copy import deepcopy
from typing import Any

def build_execution_fingerprint(composition_spec: dict[str, Any], gate: dict[str, Any], selected_text: str | None = None) -> str:
    payload = {
        "immutable_title": composition_spec.get("immutable_title") or "",
        "category": composition_spec.get("category"),
        "composition": composition_spec.get("composition") or {},
        "gate_approved": bool(gate.get("approved")),
        "gate_title": gate.get("immutable_title") or "",
        "selected_text": selected_text,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

def build_execution_receipt(result: dict[str, Any], fingerprint: str) -> dict[str, Any]:
    if len(fingerprint) != 64:
        raise ValueError("Execution fingerprint must be a SHA-256 hex digest.")
    render = result.get("render") or {}
    downstream = result.get("downstream")
    return {
        "schema_version": "0.13.0",
        "fingerprint": fingerprint,
        "backend_bound": bool(result.get("backend_bound")),
        "backend_executed": bool(result.get("backend_executed")),
        "render_status": render.get("status"),
        "artifact": deepcopy(render.get("artifact")) if render.get("artifact") else None,
        "downstream_stage": downstream.get("stage") if isinstance(downstream, dict) else None,
        "qa_status": (downstream.get("qa") or {}).get("status") if isinstance(downstream, dict) else None,
        "finalized": bool(isinstance(downstream, dict) and downstream.get("final_record")),
        "publish_executed": bool(isinstance(downstream, dict) and (downstream.get("publish_handoff") or {}).get("publish_executed")),
        "v2_write_performed": bool(isinstance(downstream, dict) and (downstream.get("publish_handoff") or {}).get("v2_write_performed")),
    }

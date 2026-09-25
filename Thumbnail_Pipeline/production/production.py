from __future__ import annotations
from typing import Any
from Thumbnail_Pipeline.db import ReceiptStore
from Thumbnail_Pipeline.execution import build_execution_fingerprint, build_execution_receipt, evaluate_idempotency_gate, require_execution_allowed, run_with_backend
from Thumbnail_Pipeline.qa import inspect_visual_qa
from Thumbnail_Pipeline.orchestration import advance_rendered_asset

def run_production_thumbnail(composition_spec: dict[str, Any], gate: dict[str, Any], *, backend: Any, visual_qa_provider: Any = None, selected_text: str | None = None, execute: bool = False, allow_rerun: bool = False, receipt_store: ReceiptStore | None = None) -> dict[str, Any]:
    store = receipt_store or ReceiptStore()
    fingerprint = build_execution_fingerprint(composition_spec, gate, selected_text)
    duplicate_gate = evaluate_idempotency_gate(fingerprint, store.receipts_for(fingerprint))
    if execute:
        require_execution_allowed(duplicate_gate, allow_rerun=allow_rerun)
    result = run_with_backend(composition_spec, gate, backend=backend, selected_text=selected_text, execute=execute)
    inspection = None
    render = result.get("render") or {}
    if render.get("status") == "rendered" and visual_qa_provider is not None:
        inspection = inspect_visual_qa(render.get("artifact"), visual_qa_provider)
        result["downstream"] = advance_rendered_asset(render, observed=inspection["observed"])
    receipt = build_execution_receipt(result, fingerprint)
    receipt_path = store.save(receipt) if execute else None
    return {"schema_version":"0.18.0","fingerprint":fingerprint,"idempotency_gate":duplicate_gate,"execution":result,"visual_qa_inspection":inspection,"receipt":receipt,"receipt_path":receipt_path.as_posix() if receipt_path else None,"publish_executed":False,"v2_write_performed":False}

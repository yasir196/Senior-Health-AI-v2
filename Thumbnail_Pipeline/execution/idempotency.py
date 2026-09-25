from __future__ import annotations
from typing import Any, Iterable

def evaluate_idempotency_gate(fingerprint: str, receipts: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
    if len(fingerprint) != 64:
        raise ValueError("Execution fingerprint must be a SHA-256 hex digest.")
    matches = [r for r in (receipts or []) if r.get("fingerprint") == fingerprint]
    completed = [r for r in matches if r.get("backend_executed") and r.get("render_status") == "rendered"]
    finalized = [r for r in completed if r.get("finalized")]
    blocked = bool(completed)
    reason = "prior_finalized_execution" if finalized else ("prior_rendered_execution" if completed else "no_prior_execution")
    return {"schema_version":"0.14.0","fingerprint":fingerprint,"duplicate_execution_blocked":blocked,"reason":reason,"matching_receipts":len(matches),"completed_executions":len(completed),"finalized_executions":len(finalized)}

def require_execution_allowed(gate: dict[str, Any], *, allow_rerun: bool = False) -> None:
    if gate.get("duplicate_execution_blocked") and not allow_rerun:
        raise ValueError("Duplicate thumbnail execution blocked by idempotency gate.")

import pytest
from Thumbnail_Pipeline.execution import evaluate_idempotency_gate, require_execution_allowed
FP="a"*64

def test_no_prior_receipt_allows_execution():
    gate=evaluate_idempotency_gate(FP,[])
    assert gate["duplicate_execution_blocked"] is False

def test_dry_run_receipt_does_not_block_execution():
    gate=evaluate_idempotency_gate(FP,[{"fingerprint":FP,"backend_executed":False,"render_status":"dry_run","finalized":False}])
    assert gate["duplicate_execution_blocked"] is False

def test_prior_rendered_execution_blocks_duplicate():
    gate=evaluate_idempotency_gate(FP,[{"fingerprint":FP,"backend_executed":True,"render_status":"rendered","finalized":False}])
    assert gate["duplicate_execution_blocked"] is True
    assert gate["reason"]=="prior_rendered_execution"

def test_prior_finalized_execution_reports_reason():
    gate=evaluate_idempotency_gate(FP,[{"fingerprint":FP,"backend_executed":True,"render_status":"rendered","finalized":True}])
    assert gate["reason"]=="prior_finalized_execution"

def test_explicit_rerun_can_pass_gate():
    gate={"duplicate_execution_blocked":True}
    with pytest.raises(ValueError):
        require_execution_allowed(gate)
    require_execution_allowed(gate,allow_rerun=True)

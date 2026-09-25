from Thumbnail_Pipeline.execution import build_execution_fingerprint, build_execution_receipt

def _spec():
    return {"immutable_title":"LOCKED","category":"mobility","composition":{"layout":"split","safe_zone":"clear"}}

def _gate():
    return {"approved":True,"immutable_title":"LOCKED"}

def test_fingerprint_is_deterministic():
    a=build_execution_fingerprint(_spec(),_gate(),"START HERE")
    b=build_execution_fingerprint(_spec(),_gate(),"START HERE")
    assert a==b
    assert len(a)==64

def test_fingerprint_changes_when_selected_text_changes():
    assert build_execution_fingerprint(_spec(),_gate(),"A") != build_execution_fingerprint(_spec(),_gate(),"B")

def test_fingerprint_changes_when_composition_changes():
    changed=_spec(); changed["composition"]["layout"]="other"
    assert build_execution_fingerprint(_spec(),_gate()) != build_execution_fingerprint(changed,_gate())

def test_dry_run_receipt_records_no_execution():
    result={"backend_bound":True,"backend_executed":False,"render":{"status":"dry_run"},"downstream":None}
    receipt=build_execution_receipt(result,"a"*64)
    assert receipt["backend_executed"] is False
    assert receipt["finalized"] is False
    assert receipt["publish_executed"] is False
    assert receipt["v2_write_performed"] is False

def test_finalized_receipt_preserves_non_publish_state():
    result={"backend_bound":True,"backend_executed":True,"render":{"status":"rendered","artifact":{"immutable_title":"LOCKED"}},"downstream":{"stage":"finalized","qa":{"status":"passed"},"final_record":{"status":"final"},"publish_handoff":{"publish_executed":False,"v2_write_performed":False}}}
    receipt=build_execution_receipt(result,"b"*64)
    assert receipt["render_status"]=="rendered"
    assert receipt["qa_status"]=="passed"
    assert receipt["finalized"] is True
    assert receipt["publish_executed"] is False

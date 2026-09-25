import pytest
from Thumbnail_Pipeline.execution import run_with_backend

def _spec():
    return {"immutable_title":"LOCKED","category":"mobility","composition":{"layout":"split","subject_placement":"right","text_placement":"left","safe_zone":"bottom_right_clear","thumbnail_text_candidates":["START HERE"]},"provenance":{"source":"test"}}

def _gate():
    return {"approved":True,"immutable_title":"LOCKED","schema_version":"0.4.0"}

class Backend:
    def __init__(self): self.calls=[]
    def generate(self,request):
        self.calls.append(request)
        return {"output_path":"Thumbnail_Pipeline/outputs/p1/thumb.png","width":1280,"height":720,"immutable_title":"LOCKED"}

def _observed():
    return {"layout_matches":True,"subject_placement_matches":True,"text_placement_matches":True,"safe_zone_clear":True}

def test_backend_is_required_even_for_binding():
    with pytest.raises(ValueError):
        run_with_backend(_spec(),_gate(),backend=None)

def test_default_backend_runner_is_still_dry_run():
    backend=Backend()
    result=run_with_backend(_spec(),_gate(),backend=backend,selected_text="START HERE")
    assert result["backend_bound"] is True
    assert result["backend_executed"] is False
    assert backend.calls==[]

def test_explicit_execute_calls_backend_once():
    backend=Backend()
    result=run_with_backend(_spec(),_gate(),backend=backend,execute=True)
    assert len(backend.calls)==1
    assert result["backend_executed"] is True
    assert result["downstream"]["qa"]["status"]=="needs_human_review"

def test_confirmed_visuals_reach_finalization_without_publish():
    backend=Backend()
    result=run_with_backend(_spec(),_gate(),backend=backend,execute=True,observed=_observed())
    assert result["downstream"]["stage"]=="finalized"
    assert result["downstream"]["publish_handoff"]["publish_executed"] is False
    assert result["downstream"]["publish_handoff"]["v2_write_performed"] is False

def test_backend_receives_immutable_title_and_reviewed_contract():
    backend=Backend()
    run_with_backend(_spec(),_gate(),backend=backend,selected_text="START HERE",execute=True)
    request=backend.calls[0]
    assert request["immutable_title"]=="LOCKED"
    assert request["instructions"]["thumbnail_text"]=="START HERE"
    assert request["instructions"]["safe_zone"]=="bottom_right_clear"

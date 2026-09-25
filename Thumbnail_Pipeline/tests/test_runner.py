import pytest
from Thumbnail_Pipeline.runner import run_render_stage

def _spec():
    return {"immutable_title":"LOCKED","category":"mobility","composition":{"layout":"split","subject_placement":"right","text_placement":"left","safe_zone":"bottom_right_clear","thumbnail_text_candidates":["START HERE"]},"provenance":{"source":"test"}}

def _gate():
    return {"approved":True,"immutable_title":"LOCKED","schema_version":"0.4.0"}

class FakeProvider:
    def __init__(self): self.calls=0
    def render(self,handoff):
        self.calls+=1
        return {"output_path":"Thumbnail_Pipeline/outputs/p1/thumb.png","width":1280,"height":720,"immutable_title":"LOCKED"}

def _observed():
    return {"layout_matches":True,"subject_placement_matches":True,"text_placement_matches":True,"safe_zone_clear":True}

def test_default_runner_is_dry_run_and_never_calls_provider():
    provider=FakeProvider()
    result=run_render_stage(_spec(),_gate(),selected_text="START HERE",provider=provider)
    assert result["render"]["status"]=="dry_run"
    assert result["downstream"] is None
    assert provider.calls==0

def test_execute_requires_provider():
    with pytest.raises(ValueError):
        run_render_stage(_spec(),_gate(),execute=True)

def test_execute_with_unknown_visuals_stops_at_human_review():
    result=run_render_stage(_spec(),_gate(),provider=FakeProvider(),execute=True)
    assert result["downstream"]["qa"]["status"]=="needs_human_review"
    assert result["downstream"]["final_record"] is None

def test_execute_with_confirmed_visuals_reaches_finalization_not_publish():
    provider=FakeProvider()
    result=run_render_stage(_spec(),_gate(),selected_text="START HERE",provider=provider,execute=True,observed=_observed())
    assert provider.calls==1
    assert result["downstream"]["stage"]=="finalized"
    assert result["downstream"]["publish_handoff"]["publish_executed"] is False
    assert result["downstream"]["publish_handoff"]["v2_write_performed"] is False

def test_runner_preserves_immutable_title():
    result=run_render_stage(_spec(),_gate(),provider=FakeProvider(),execute=True,observed=_observed())
    assert result["handoff"]["immutable_title"]=="LOCKED"
    assert result["downstream"]["final_record"]["immutable_title"]=="LOCKED"

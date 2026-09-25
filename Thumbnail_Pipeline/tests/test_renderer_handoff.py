import pytest

from Thumbnail_Pipeline.generation import build_generation_handoff
from Thumbnail_Pipeline.renderer import dispatch_renderer


def _reviewed_spec():
    return {
        "immutable_title":"LOCKED",
        "category":"mobility",
        "composition":{
            "layout":"text_left_subject_right",
            "thumbnail_text_candidates":["DO THIS FIRST","START HERE"],
            "subject_placement":"right",
            "text_placement":"left",
            "safe_zone":"bottom_right_clear",
        },
        "provenance":{"source":"phase2_concept_direction"},
    }


def _gate():
    return {"schema_version":"0.4.0","approved":True,"immutable_title":"LOCKED"}


def test_handoff_requires_approved_gate():
    with pytest.raises(ValueError):
        build_generation_handoff(_reviewed_spec(),{"approved":False,"immutable_title":"LOCKED"})


def test_handoff_preserves_title_and_reviewed_contract():
    handoff=build_generation_handoff(_reviewed_spec(),_gate(),selected_text="DO THIS FIRST")
    assert handoff["immutable_title"]=="LOCKED"
    assert handoff["render_contract"]["layout"]=="text_left_subject_right"
    assert handoff["render_contract"]["thumbnail_text"]=="DO THIS FIRST"
    assert handoff["renderer_status"]=="not_invoked"


def test_unreviewed_text_cannot_enter_handoff():
    with pytest.raises(ValueError):
        build_generation_handoff(_reviewed_spec(),_gate(),selected_text="NEW COPY")


def test_renderer_defaults_to_dry_run_and_does_not_call_provider():
    class ExplodingProvider:
        def render(self, handoff):
            raise AssertionError("provider must not be called in dry run")
    handoff=build_generation_handoff(_reviewed_spec(),_gate())
    result=dispatch_renderer(handoff,provider=ExplodingProvider())
    assert result["status"]=="dry_run"
    assert result["renderer_invoked"] is False


def test_execute_requires_explicit_provider():
    handoff=build_generation_handoff(_reviewed_spec(),_gate())
    with pytest.raises(ValueError):
        dispatch_renderer(handoff,execute=True)


def test_explicit_execute_calls_provider_once():
    class FakeProvider:
        def __init__(self): self.calls=0
        def render(self,handoff):
            self.calls+=1
            return {"asset_id":"fake-1","output_path":"Thumbnail_Pipeline/outputs/test/fake-1.png","width":1280,"height":720,"mime_type":"image/png","immutable_title":"LOCKED"}
    provider=FakeProvider()
    handoff=build_generation_handoff(_reviewed_spec(),_gate(),selected_text="START HERE")
    result=dispatch_renderer(handoff,provider=provider,execute=True)
    assert provider.calls==1
    assert result["renderer_invoked"] is True
    assert result["artifact"]["asset"]["asset_id"]=="fake-1"
    assert result["artifact"]["qa_status"]=="pending"

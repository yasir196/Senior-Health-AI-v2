import pytest
from Thumbnail_Pipeline.qa import build_visual_qa_request, inspect_visual_qa, evaluate_post_render_qa

def artifact():
    return {"immutable_title":"LOCKED","asset":{"output_path":"Thumbnail_Pipeline/outputs/x.png","width":1280,"height":720},"render_contract":{"layout":"split","subject_placement":"right","text_placement":"left","safe_zone":"bottom_right_clear"}}

class Provider:
    def __init__(self,result): self.result=result; self.calls=[]
    def inspect(self,request): self.calls.append(request); return self.result

def test_request_contains_asset_and_expected_contract():
    r=build_visual_qa_request(artifact())
    assert r["asset"]["output_path"].endswith("x.png")
    assert r["expected"]["safe_zone"]=="bottom_right_clear"

def test_complete_provider_observations_can_feed_existing_qa():
    p=Provider({"layout_matches":True,"subject_placement_matches":True,"text_placement_matches":True,"safe_zone_clear":True,"evidence":{"source":"vision"}})
    inspection=inspect_visual_qa(artifact(),p)
    qa=evaluate_post_render_qa(artifact(),observed=inspection["observed"])
    assert inspection["complete"] is True
    assert qa["status"]=="passed"

def test_partial_provider_result_stays_incomplete():
    p=Provider({"layout_matches":True})
    inspection=inspect_visual_qa(artifact(),p)
    assert inspection["complete"] is False
    assert inspection["observed"]["safe_zone_clear"] is None

def test_explicit_visual_failure_is_preserved():
    p=Provider({"layout_matches":True,"subject_placement_matches":False,"text_placement_matches":True,"safe_zone_clear":True})
    inspection=inspect_visual_qa(artifact(),p)
    qa=evaluate_post_render_qa(artifact(),observed=inspection["observed"])
    assert qa["status"]=="failed"

def test_non_mapping_provider_result_rejected():
    class Bad:
        def inspect(self,request): return "yes"
    with pytest.raises(ValueError): inspect_visual_qa(artifact(),Bad())

def test_unresolved_contract_rejected_before_provider():
    a=artifact(); a["render_contract"]["safe_zone"]=None
    with pytest.raises(ValueError): build_visual_qa_request(a)

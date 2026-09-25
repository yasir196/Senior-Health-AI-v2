import pytest
from Thumbnail_Pipeline.orchestration import advance_rendered_asset

def _artifact():
    return {"asset":{"output_path":"Thumbnail_Pipeline/outputs/p1/thumb.png","width":1280,"height":720},"immutable_title":"LOCKED","render_contract":{"layout":"text_left_subject_right","subject_placement":"right","text_placement":"left","safe_zone":"bottom_right_clear"},"provenance":{"source":"phase2_concept_direction"},"qa_status":"pending"}

def _rendered():
    return {"status":"rendered","renderer_invoked":True,"artifact":_artifact()}

def _observed():
    return {"layout_matches":True,"subject_placement_matches":True,"text_placement_matches":True,"safe_zone_clear":True}

def test_orchestrator_rejects_dry_run():
    with pytest.raises(ValueError):
        advance_rendered_asset({"status":"dry_run","renderer_invoked":False})

def test_unknown_visual_checks_stop_before_finalization():
    result=advance_rendered_asset(_rendered())
    assert result["stage"]=="post_render_qa"
    assert result["qa"]["status"]=="needs_human_review"
    assert result["final_record"] is None

def test_failed_visual_check_stops_before_finalization():
    result=advance_rendered_asset(_rendered(),observed={"safe_zone_clear":False})
    assert result["qa"]["status"]=="failed"
    assert result["final_record"] is None

def test_confirmed_visual_checks_finalize_but_do_not_publish():
    result=advance_rendered_asset(_rendered(),observed=_observed())
    assert result["stage"]=="finalized"
    assert result["final_record"]["status"]=="final"
    assert result["publish_handoff"]["publish_executed"] is False
    assert result["publish_handoff"]["v2_write_performed"] is False

def test_title_is_preserved_through_orchestration():
    result=advance_rendered_asset(_rendered(),observed=_observed())
    assert result["final_record"]["immutable_title"]=="LOCKED"
    assert result["publish_handoff"]["immutable_title"]=="LOCKED"

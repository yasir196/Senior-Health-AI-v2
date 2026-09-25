import pytest

from Thumbnail_Pipeline.qa import evaluate_post_render_qa, apply_post_render_review


def _artifact():
    return {
        "asset":{"output_path":"Thumbnail_Pipeline/outputs/p1/thumb.png","width":1280,"height":720},
        "immutable_title":"LOCKED",
        "render_contract":{
            "layout":"text_left_subject_right",
            "subject_placement":"right",
            "text_placement":"left",
            "safe_zone":"bottom_right_clear",
        },
        "qa_status":"pending",
    }


def test_post_render_qa_does_not_invent_visual_observations():
    qa=evaluate_post_render_qa(_artifact())
    assert qa["status"]=="needs_human_review"
    assert qa["final_asset_accepted"] is False
    assert len(qa["human_review_required_for"])==4
    assert all(value is None for value in qa["checks"]["visual"].values())


def test_explicit_visual_failure_blocks_asset():
    qa=evaluate_post_render_qa(_artifact(),observed={"safe_zone_clear":False})
    assert qa["status"]=="failed"
    assert qa["final_asset_accepted"] is False


def test_all_confirmed_visual_checks_accept_asset():
    observed={
        "layout_matches":True,
        "subject_placement_matches":True,
        "text_placement_matches":True,
        "safe_zone_clear":True,
    }
    qa=evaluate_post_render_qa(_artifact(),observed=observed)
    assert qa["status"]=="passed"
    assert qa["final_asset_accepted"] is True
    assert qa["human_review_required_for"]==[]


def test_missing_render_contract_field_fails_structural_gate():
    artifact=_artifact()
    artifact["render_contract"]["safe_zone"]=None
    qa=evaluate_post_render_qa(artifact(), observed={}) if False else evaluate_post_render_qa(artifact)
    assert qa["status"]=="failed"
    assert "safe_zone" in qa["checks"]["contract_failures"]


def test_human_review_can_resolve_only_pending_fields():
    artifact=_artifact()
    qa=evaluate_post_render_qa(artifact,observed={"layout_matches":True})
    reviewed=apply_post_render_review(artifact,qa,decisions={
        "subject_placement_matches":True,
        "text_placement_matches":True,
        "safe_zone_clear":True,
    },notes="visual contract confirmed")
    assert reviewed["status"]=="passed"
    assert reviewed["final_asset_accepted"] is True


def test_human_review_rejects_non_pending_field_override():
    artifact=_artifact()
    qa=evaluate_post_render_qa(artifact,observed={"layout_matches":False})
    with pytest.raises(ValueError):
        apply_post_render_review(artifact,qa,decisions={"layout_matches":True})

import pytest

from Thumbnail_Pipeline.qa import apply_composition_review, evaluate_generation_gate


def _spec():
    return {
        "immutable_title":"LOCKED",
        "status":"ready_for_prompt_review",
        "composition":{
            "layout":"text_left_subject_right",
            "thumbnail_text_candidates":["DO THIS FIRST"],
            "subject_placement":None,
            "text_placement":None,
            "safe_zone":None,
        },
        "constraints":{"title_must_remain_unchanged":True,"generation_allowed":False,"renderer_allowed":False},
        "human_review_required_for":["subject_placement","text_placement","safe_zone"],
    }


def test_generation_gate_stays_closed_with_unresolved_fields():
    gate=evaluate_generation_gate(_spec())
    assert gate["approved"] is False
    assert gate["renderer_invoked"] is False
    assert gate["unresolved_fields"]==["subject_placement","text_placement","safe_zone"]


def test_human_review_resolves_fields_then_gate_can_approve_without_rendering():
    reviewed=apply_composition_review(_spec(),corrections={
        "subject_placement":"right",
        "text_placement":"left",
        "safe_zone":"bottom_right_clear",
    },notes="approved composition")
    assert reviewed["immutable_title"]=="LOCKED"
    assert reviewed["status"]=="review_complete"
    assert reviewed["human_review_required_for"]==[]
    assert reviewed["constraints"]["generation_allowed"] is False
    gate=evaluate_generation_gate(reviewed)
    assert gate["approved"] is True
    assert gate["renderer_invoked"] is False


def test_review_rejects_unknown_fields_and_cannot_rewrite_title():
    with pytest.raises(ValueError):
        apply_composition_review(_spec(),corrections={"immutable_title":"CHANGED"})

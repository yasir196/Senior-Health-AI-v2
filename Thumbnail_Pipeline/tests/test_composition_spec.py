from Thumbnail_Pipeline.composition import build_composition_spec, build_prompt_spec


def test_composition_spec_preserves_title_and_does_not_invent_layout():
    direction={
        "immutable_title":"LOCKED TITLE",
        "evidence_status":"no_winner_evidence",
        "concept":{"category":"mobility","composition_layout":None,"thumbnail_text_examples":[]},
        "evidence":{"channel_winner_count":0,"youtube_reference_count":2},
        "constraints":{"title_must_remain_unchanged":True,"external_references_are_secondary":True},
    }
    spec=build_composition_spec(direction)
    assert spec["immutable_title"]=="LOCKED TITLE"
    assert spec["composition"]["layout"] is None
    assert spec["status"]=="needs_human_direction"
    assert "layout" in spec["human_review_required_for"]
    assert spec["constraints"]["generation_allowed"] is False


def test_composition_spec_carries_supported_winner_layout_and_text():
    direction={
        "immutable_title":"LOCKED",
        "evidence_status":"winner_supported",
        "concept":{"category":"mobility","composition_layout":"text_left_subject_right","thumbnail_text_examples":["DO THIS FIRST","START HERE"]},
        "evidence":{"channel_winner_count":3,"youtube_reference_count":4},
        "constraints":{"title_must_remain_unchanged":True},
    }
    spec=build_composition_spec(direction)
    assert spec["composition"]["layout"]=="text_left_subject_right"
    assert spec["composition"]["thumbnail_text_candidates"]==["DO THIS FIRST","START HERE"]
    assert spec["provenance"]["layout_supported_by_winner_evidence"] is True
    assert "layout" not in spec["human_review_required_for"]
    prompt=build_prompt_spec(spec)
    assert prompt["immutable_title"]=="LOCKED"
    assert prompt["generation_allowed"] is False
    assert prompt["prompt_contract"]["layout"]=="text_left_subject_right"

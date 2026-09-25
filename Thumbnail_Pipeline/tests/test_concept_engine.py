from Thumbnail_Pipeline.concept_engine import build_concept_direction


def test_concept_engine_preserves_title_and_does_not_invent_missing_fields():
    ctx={
        "immutable_title":"Can’t Stand Up Easily After 60? Do These 5 Chair Exercises Daily.",
        "requested_category":"mobility",
        "winner_prior":{"winner_examples":[]},
        "youtube_examples":[],
    }
    out=build_concept_direction(ctx)
    assert out["immutable_title"]==ctx["immutable_title"]
    assert out["evidence_status"]=="no_winner_evidence"
    assert out["concept"]["composition_layout"] is None
    assert out["constraints"]["generation_allowed"] is False


def test_concept_engine_uses_winner_evidence_without_copying_losers():
    ctx={
        "immutable_title":"Locked Title",
        "requested_category":"mobility",
        "winner_prior":{"winner_examples":[
            {"thumbnail_text":"DO THIS FIRST","composition_layout":"text_left_subject_right","v2_analysis":{"hero_category":"mobility"}},
            {"thumbnail_text":"START RIGHT HERE","composition_layout":"text_left_subject_right","v2_analysis":{"hero_category":"mobility"}},
        ]},
        "youtube_examples":[{"video_id":"external-1"}],
        "loser_examples":[{"thumbnail_text":"LOSER COPY"}],
    }
    out=build_concept_direction(ctx)
    assert out["evidence_status"]=="winner_supported"
    assert out["concept"]["composition_layout"]=="text_left_subject_right"
    assert "LOSER COPY" not in out["concept"]["thumbnail_text_examples"]
    assert out["evidence"]["youtube_reference_count"]==1
    assert out["immutable_title"]=="Locked Title"

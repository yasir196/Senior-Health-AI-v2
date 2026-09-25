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


def test_concept_engine_uses_category_packaging_associations_before_channel():
    def row(context, feature, value, weight=1.0):
        return {"context_type":context,"feature_name":feature,"feature_value":value,
                "association_direction":"positive","evidence_weight":weight,
                "video_count":10,"total_impressions":10000,"ctr_delta_points":1.0}
    ctx={
        "immutable_title":"Locked",
        "requested_category":"food",
        "winner_prior":{"winner_examples":[]},
        "packaging_associations":{
            "run":{"id":10},
            "category":[
                row("hero_category","composition_layout","category_layout"),
                row("hero_category","presenter_position","right"),
                row("hero_category","text_style","bold_condensed"),
            ],
            "channel":[
                row("channel","composition_layout","channel_layout"),
                row("channel","presenter_position","left"),
            ],
        },
    }
    out=build_concept_direction(ctx)
    assert out["evidence_status"]=="association_supported"
    assert out["concept"]["composition_layout"]=="category_layout"
    assert out["concept"]["presenter_position"]=="right"
    assert out["concept"]["text_style"]=="bold_condensed"

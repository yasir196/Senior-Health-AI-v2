import pytest

from Thumbnail_Pipeline.generation.handoff import build_generation_handoff


def _spec():
    return {
        "immutable_title":"Example title",
        "category":"health",
        "composition":{
            "thumbnail_text_candidates":["OLD REVIEWED COPY"],
            "layout":"text_left_subject_right",
            "subject_placement":"right",
            "text_placement":"left",
            "safe_zone":"bottom-right clear",
        },
    }


def _gate():
    return {"approved":True,"immutable_title":"Example title","schema_version":"test"}


def test_handoff_accepts_explicitly_authorized_psychology_copy():
    result=build_generation_handoff(
        _spec(),_gate(),
        selected_text="WHAT ONE MOVE TELLS",
        selected_text_authorized=True,
    )
    assert result["render_contract"]["thumbnail_text"]=="WHAT ONE MOVE TELLS"


def test_handoff_still_rejects_unreviewed_copy_without_authorization():
    with pytest.raises(ValueError,match="reviewed candidates or explicit downstream authorization"):
        build_generation_handoff(
            _spec(),_gate(),
            selected_text="UNREVIEWED COPY",
            selected_text_authorized=False,
        )


def test_handoff_legacy_reviewed_candidate_still_passes():
    result=build_generation_handoff(_spec(),_gate(),selected_text="OLD REVIEWED COPY")
    assert result["render_contract"]["thumbnail_text"]=="OLD REVIEWED COPY"

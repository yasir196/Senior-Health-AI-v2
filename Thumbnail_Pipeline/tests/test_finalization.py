import pytest

from Thumbnail_Pipeline.finalization import finalize_thumbnail_asset, build_publish_handoff


def _artifact():
    return {
        "asset":{"output_path":"Thumbnail_Pipeline/outputs/p1/thumb.png","width":1280,"height":720,"asset_id":"a1"},
        "immutable_title":"LOCKED",
        "render_contract":{"layout":"text_left_subject_right"},
        "provenance":{"source":"phase2_concept_direction"},
    }


def _qa():
    return {
        "schema_version":"0.7.0",
        "status":"passed",
        "immutable_title":"LOCKED",
        "checks":{"visual":{"safe_zone_clear":True}},
        "human_review":{"status":"reviewed"},
        "final_asset_accepted":True,
    }


def test_finalize_requires_passed_accepted_qa():
    qa=_qa()
    qa["status"]="failed"
    qa["final_asset_accepted"]=False
    with pytest.raises(ValueError):
        finalize_thumbnail_asset(_artifact(),qa)


def test_finalize_rejects_title_mismatch():
    qa=_qa()
    qa["immutable_title"]="CHANGED"
    with pytest.raises(ValueError):
        finalize_thumbnail_asset(_artifact(),qa)


def test_finalize_preserves_isolated_asset_and_provenance():
    final=finalize_thumbnail_asset(_artifact(),_qa())
    assert final["status"]=="final"
    assert final["asset"]["output_path"]=="Thumbnail_Pipeline/outputs/p1/thumb.png"
    assert final["immutable_title"]=="LOCKED"
    assert final["publish_status"]=="not_published"
    assert final["v2_write_performed"] is False


def test_publish_handoff_is_non_executing_and_v2_read_only():
    final=finalize_thumbnail_asset(_artifact(),_qa())
    handoff=build_publish_handoff(final)
    assert handoff["status"]=="ready_for_explicit_publish_action"
    assert handoff["publish_executed"] is False
    assert handoff["v2_write_performed"] is False


def test_publish_handoff_rejects_non_final_record():
    record={"status":"pending"}
    with pytest.raises(ValueError):
        build_publish_handoff(record)

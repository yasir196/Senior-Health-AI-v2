import pytest
from Thumbnail_Pipeline.prompt_export import export_final_thumbnail_prompt

def spec():
    return {"immutable_title":"Can't Sit on the Floor After 60? Try These 3 Simple Exercises","category":"mobility","composition":{"layout":"split","subject_placement":"right","text_placement":"left","safe_zone":"bottom_right_clear","thumbnail_text_candidates":["START HERE"]},"provenance":{"source":"test"}}
def gate(): return {"approved":True,"immutable_title":spec()["immutable_title"],"schema_version":"0.4.0"}

def test_exports_final_prompt_without_generation():
    r=export_final_thumbnail_prompt(spec(),gate(),selected_text="START HERE")
    assert "Create a 16:9 YouTube thumbnail" in r["final_prompt"]
    assert "THUMBNAIL TEXT (exact): START HERE" in r["final_prompt"]
    assert r["image_generation_executed"] is False

def test_title_is_immutable_and_present_as_context():
    r=export_final_thumbnail_prompt(spec(),gate(),selected_text="START HERE")
    assert r["immutable_title"]==spec()["immutable_title"]
    assert spec()["immutable_title"] in r["final_prompt"]

def test_rejects_unreviewed_text():
    with pytest.raises(ValueError):
        export_final_thumbnail_prompt(spec(),gate(),selected_text="NEW TEXT")

def test_rejects_unresolved_composition():
    s=spec(); s["composition"]["safe_zone"]=None
    with pytest.raises(ValueError):
        export_final_thumbnail_prompt(s,gate(),selected_text="START HERE")

def test_never_uploads_or_writes_v2():
    r=export_final_thumbnail_prompt(spec(),gate(),selected_text="START HERE")
    assert r["youtube_upload_executed"] is False
    assert r["v2_write_performed"] is False

from Thumbnail_Pipeline.qa.thumbnail_verifier import verify_thumbnail

def test_verifier_fails_explicit_mismatch():
    r=verify_thumbnail(requested={"aspect_ratio":"16:9","thumbnail_text":"DO THIS FIRST","human_count":1,"safe_zone_clear":True},observed={"aspect_ratio":"16:9","thumbnail_text":"DO THIS","human_count":2,"safe_zone_clear":True})
    assert r["verdict"]=="FAIL"
    assert "thumbnail_text" in r["failed_requirements"]
    assert "human_count" in r["failed_requirements"]

def test_verifier_does_not_fake_pass_when_observation_missing():
    r=verify_thumbnail(requested={"presenter_position":"right","safe_zone_clear":True},observed={"presenter_position":"right"})
    assert r["verdict"]=="NEEDS_REVIEW"
    assert "safe_zone_clear" in r["needs_review"]

def test_forbidden_item_check():
    r=verify_thumbnail(requested={"forbidden_items":["doctor_cues"]},observed={"forbidden_items_detected":{"doctor_cues":True}})
    assert r["verdict"]=="FAIL"
    assert "forbidden:doctor_cues" in r["failed_requirements"]

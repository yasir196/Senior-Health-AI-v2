from Thumbnail_Pipeline.qa.thumbnail_verifier import verify_thumbnail

def test_verifier_uses_ai_audit_edit_contract():
    contract={"audit_id":7,"aspect_ratio":"16:9","proposed_thumbnail_text":"DO THIS FIRST","human_count":1,"repair_checks":[{"name":"reduce_clutter","expected":True}]}
    observed={"aspect_ratio":"16:9","thumbnail_text":"DO THIS","human_count":1,"repair_checks":{"reduce_clutter":False}}
    r=verify_thumbnail(audit_edit_contract=contract,observed=observed)
    assert r["verification_source"]=="ai_audit_loser_edit_contract"
    assert r["audit_id"]==7
    assert r["verdict"]=="FAIL"
    assert "proposed_thumbnail_text" in r["failed_requirements"]
    assert "repair:reduce_clutter" in r["failed_requirements"]

def test_missing_audit_requirement_observation_needs_review():
    r=verify_thumbnail(audit_edit_contract={"audit_id":8,"safe_zone_clear":True},observed={})
    assert r["verdict"]=="NEEDS_REVIEW"

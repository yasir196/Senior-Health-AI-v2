from Thumbnail_Pipeline.intelligence.new_project_prior import build_new_project_prior

def row(cat,title,ctr=7.0,imp=5000,weight=1.0):
    return {"performance":{"title":title,"ctr":ctr,"impressions":imp,"evidence_weight":weight},"ocr":{"text":"WIN"},"v2_analysis":{"hero_category":cat}}

def test_new_project_prefers_same_category_winners():
    r=build_new_project_prior(category="mobility",winner_rows=[row("mobility","M"),row("nutrition","N",9)])
    assert r["selected_winner_category"]=="mobility"
    assert r["fallback_to_strongest_winner_category"] is False

def test_missing_category_uses_strongest_winner_category_not_loser():
    r=build_new_project_prior(category="sleep",winner_rows=[row("mobility","M",6,10000),row("nutrition","N",8,8000)])
    assert r["status"]=="READY"
    assert r["selected_winner_category"]=="nutrition"
    assert r["fallback_to_strongest_winner_category"] is True
    assert r["loser_fallback_allowed"] is False

def test_no_winners_at_all_reports_no_winner_evidence():
    r=build_new_project_prior(category="mobility",winner_rows=[])
    assert r["status"]=="NO_WINNER_EVIDENCE"

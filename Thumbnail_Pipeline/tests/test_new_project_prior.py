from Thumbnail_Pipeline.intelligence.new_project_prior import build_new_project_prior

def row(cat,title):
    return {"performance":{"title":title,"ctr":7.0,"impressions":5000},"ocr":{"text":"WIN"},"v2_analysis":{"hero_category":cat}}

def test_new_project_uses_same_category_winners_only():
    r=build_new_project_prior(category="mobility",winner_rows=[row("mobility","M"),row("nutrition","N")])
    assert r["status"]=="READY"
    assert [x["title"] for x in r["winner_examples"]]==["M"]
    assert r["loser_fallback_allowed"] is False

def test_new_project_never_falls_back_to_loser_lane():
    r=build_new_project_prior(category="mobility",winner_rows=[])
    assert r["status"]=="INSUFFICIENT_WINNER_EVIDENCE"
    assert r["loser_fallback_allowed"] is False

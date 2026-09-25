from Thumbnail_Pipeline.intelligence.youtube_outlier_contract import build_youtube_outlier_brief,combine_new_project_evidence

def test_search_is_cross_channel_and_outlier_optional():
    b=build_youtube_outlier_brief(title="T",category="mobility")
    r=b["search_requirements"]
    assert r["same_topic_first"] is True
    assert r["same_category_expand"] is True
    assert r["same_channel_only"] is False
    assert r["outlier_required"] is False
    assert r["inspect_title_and_thumbnail_together"] is True

def test_channel_winners_remain_primary():
    c=combine_new_project_evidence(winner_prior={"status":"READY"},youtube_examples=[{"video_title":"X"}])
    assert c["primary_learning_source"]=="channel_winners"

from Thumbnail_Pipeline.intelligence.youtube_outlier import annotate_outliers,rank_references

def test_comparative_strength_uses_scope_median():
    rows=[{"search_scope":"same_topic","video_id":str(i),"views":v} for i,v in enumerate([100,100,100,100,100,1000])]
    a=annotate_outliers(rows,minimum_comparison_videos=5)
    big=next(x for x in a if x["views"]==1000)
    assert big["outlier_status"]=="comparative_evidence_available"
    assert big["outlier_evidence"]["views_vs_median_multiple"]==10.0

def test_small_sample_does_not_claim_outlier():
    a=annotate_outliers([{"search_scope":"same_topic","views":100},{"search_scope":"same_topic","views":1000}],minimum_comparison_videos=5)
    assert all(x["outlier_status"]=="not_claimed" for x in a)

def test_same_topic_ranks_before_category():
    rows=[{"search_scope":"same_category","views":9999},{"search_scope":"same_topic","views":100}]
    assert rank_references(rows)[0]["search_scope"]=="same_topic"

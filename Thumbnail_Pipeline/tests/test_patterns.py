from Thumbnail_Pipeline.intelligence.patterns import build_patterns,classify_category,reliability_weight

def row(title,ctr,impressions,words,clutter,category="mobility",evidence_weight=None):
    perf={"title":title,"ctr":ctr,"impressions":impressions}
    if evidence_weight is not None: perf["evidence_weight"]=evidence_weight
    return {"features":{"clutter_score":clutter,"brightness_mean":90},"ocr":{"word_count":words,"line_count":3},"performance":perf,"v2_analysis":{"hero_category":category}}

def test_category_classifier_uses_v2_category_not_title_keywords():
    assert classify_category(row("Anything",5,1000,3,.2,"exercise_mobility"))=="exercise_mobility"
    assert classify_category("3 Chair Exercises After 60")=="uncategorized"

def test_low_impressions_are_excluded():
    result=build_patterns([row("A",9,300,3,.2),row("B",6,20000,4,.3)])
    assert result["eligible_observations"]==1 and result["excluded_observations"]==1

def test_comparisons_are_within_category():
    result=build_patterns([row("A",8,10000,3,.2,"exercise"),row("B",4,10000,7,.6,"exercise"),row("C",7,10000,4,.3,"food"),row("D",3,10000,8,.7,"food")])
    assert result["category_patterns"]["exercise"]["median_ctr"]==6.0
    assert result["category_patterns"]["food"]["median_ctr"]==5.0

def test_reliability_prefers_v2_evidence_weight():
    assert reliability_weight(row("A",5,2000,3,.2,evidence_weight=.37))==.37

def test_reliability_fallback_reads_configured_1000_to_10000_range():
    assert reliability_weight(row("A",5,1000,3,.2))==0
    assert 0<reliability_weight(row("A",5,2000,3,.2))<1
    assert reliability_weight(row("A",5,10000,3,.2))==1

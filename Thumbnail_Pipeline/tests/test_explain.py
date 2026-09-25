from Thumbnail_Pipeline.intelligence.explain import explain_group_difference

def test_explanation_reports_observed_direction_without_semantic_good_bad_label():
    high={"feature_medians":{"ocr_word_count":4,"clutter_score":.2,"contrast_std":80}}
    low={"feature_medians":{"ocr_word_count":8,"clutter_score":.6,"contrast_std":50}}
    findings=explain_group_difference(high,low)
    by={x["feature"]:x for x in findings}
    assert by["ocr_word_count"]["direction_in_higher_ctr_group"]=="lower"
    assert by["clutter_score"]["interpretation"]=="observed_difference_only"
    assert by["contrast_std"]["interpretation"]=="observed_difference_only"
    assert all(x["claim_strength"]=="association_only" for x in findings)

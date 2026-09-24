from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from Thumbnail_Pipeline.intelligence.explain import explain_group_difference


def test_explanation_identifies_large_differences():
    high = {"feature_medians": {"ocr_word_count": 4, "clutter_score": .2, "contrast_std": 80}}
    low = {"feature_medians": {"ocr_word_count": 8, "clutter_score": .6, "contrast_std": 50}}
    findings = explain_group_difference(high, low)
    by_name = {x["feature"]: x for x in findings}
    assert by_name["ocr_word_count"]["direction_in_higher_ctr_group"] == "lower"
    assert by_name["clutter_score"]["interpretation"] == "simpler_in_higher_ctr_group"
    assert by_name["contrast_std"]["interpretation"] == "stronger_in_higher_ctr_group"
    assert all(x["claim_strength"] == "association_only" for x in findings)

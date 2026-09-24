from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from Thumbnail_Pipeline.intelligence.patterns import build_patterns, classify_category, reliability_weight


def row(title, ctr, impressions, words, clutter):
    return {
        "features": {"clutter_score": clutter, "brightness_mean": 90},
        "ocr": {"word_count": words, "line_count": 3},
        "performance": {"title": title, "ctr": ctr, "impressions": impressions},
    }


def test_category_classifier():
    assert classify_category("3 Chair Exercises After 60") == "exercise_mobility"
    assert classify_category("What Happens When You Eat Peanut Butter?") == "food_nutrition"


def test_low_impressions_are_excluded():
    result = build_patterns([
        row("Chair Exercise", 9.0, 300, 3, .2),
        row("Chair Exercise", 6.0, 20000, 4, .3),
    ])
    assert result["eligible_observations"] == 1
    assert result["excluded_observations"] == 1


def test_comparisons_are_within_category():
    result = build_patterns([
        row("Chair Exercise A", 8.0, 10000, 3, .2),
        row("Chair Exercise B", 4.0, 10000, 7, .6),
        row("Calcium Food A", 7.0, 10000, 4, .3),
        row("Calcium Food B", 3.0, 10000, 8, .7),
    ])
    exercise = result["category_patterns"]["exercise_mobility"]
    food = result["category_patterns"]["food_nutrition"]
    assert exercise["median_ctr"] == 6.0
    assert food["median_ctr"] == 5.0
    assert result["winner_patterns"]["feature_medians"]["ocr_word_count"] == 3.5


def test_reliability_requires_impressions():
    assert reliability_weight(500) == 0
    assert 0 < reliability_weight(2000) < 1
    assert reliability_weight(100000) == 1

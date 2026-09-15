from pathlib import Path
import analytics_db as adb


def test_active_promotion_requires_three_video_comparison_cohort():
    src = Path(adb.__file__).read_text(encoding='utf-8')
    assert "Both cohorts need at least" in src
    assert "PACKAGING_PROMOTION_MIN_VIDEOS_PER_COHORT = 3" in src


def test_active_promotion_blocks_uncertain_historical_thumbnail_attribution():
    src = Path(adb.__file__).read_text(encoding='utf-8')
    assert "Both cohorts must use clean post-snapshot CTR/impressions windows" in src
    assert "packaging_rule_promotion_audit" in src


def test_active_promotion_requires_two_sided_impression_support_and_delta_screen():
    src = Path(adb.__file__).read_text(encoding='utf-8')
    assert "PACKAGING_PROMOTION_MIN_IMPRESSIONS_PER_COHORT = 1000.0" in src
    assert "approximate 95% CTR-delta interval" in src

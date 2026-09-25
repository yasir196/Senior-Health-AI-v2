from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]

def test_intelligence_policy_is_configured_not_embedded_in_patterns_code():
    code=(ROOT/"intelligence"/"patterns.py").read_text(encoding="utf-8")
    assert "CATEGORY_KEYWORDS" not in code
    assert "floor: int = 1000" not in code
    assert "full: int = 10000" not in code

def test_config_owns_impression_thresholds_and_v2_category():
    cfg=json.loads((ROOT/"config"/"intelligence.json").read_text(encoding="utf-8"))
    assert cfg["categorization"]["primary_source"]=="v2_analysis.hero_category"
    assert cfg["categorization"]["keyword_fallback_enabled"] is False
    assert cfg["eligibility"]["min_impressions"]==1000
    assert cfg["reliability"]["impression_floor"]==1000
    assert cfg["reliability"]["full_reliability_impressions"]==10000

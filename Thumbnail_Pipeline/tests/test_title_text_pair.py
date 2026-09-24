from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from Thumbnail_Pipeline.intelligence.title_text_pair import pair_features, hook_type


def test_title_thumbnail_pair_detects_overlap_and_new_info():
    p = pair_features("Swollen Legs at Night? Try These Bed Movements", "ONE LEG OR BOTH?")
    assert "leg" in p["shared_keywords"] or "legs" in p["new_thumbnail_keywords"]
    assert p["thumbnail_adds_new_information"] is True


def test_hook_types():
    assert hook_type("WHAT HAPPENS NEXT?") == "question"
    assert hook_type("DO THIS FIRST") == "action"
    assert hook_type("MISSED CLUE") == "curiosity_gap"

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
from Thumbnail_Pipeline.intelligence.loser_edit_prompt import build_loser_edit_prompt

def test_full_loser_edit_prompt_contains_required_evidence():
    p = build_loser_edit_prompt(
        title="Swollen Legs at Night? Try These Bed Movements",
        original_text="OLD TEXT HERE",
        proposed_text="ONE LEG OR BOTH?",
        loser_reasons=[{"feature":"clutter_score","value":0.7,"reason":"higher than category winners"}],
        winner_evidence=[{"title":"Winner","thumbnail_text":"DO THIS FIRST","ctr":7.1,"impressions":22000}],
        original_visual={"clutter_score":0.7},
        target_visual={"layout":"text left, one subject right"},
    )
    assert "OLD TEXT HERE" in p
    assert "ONE LEG OR BOTH?" in p
    assert "Swollen Legs at Night?" in p
    assert "clutter_score" in p
    assert "DO THIS FIRST" in p
    assert "CTR: 7.1" in p
    assert "Treat the supplied original thumbnail as the image to edit" in p

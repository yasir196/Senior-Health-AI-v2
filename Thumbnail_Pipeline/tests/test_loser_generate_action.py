from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
from Thumbnail_Pipeline.dashboard.loser_actions import loser_repair_card

def test_loser_card_exposes_editable_prompt_and_generate_button():
    card = loser_repair_card(
        audit_id=7, title="Chair Exercise", original_text="OLD TEXT", why=[],
        suggestion={"basis":"winner pattern"}, proposed_text="DO THIS FIRST",
        editable_prompt="Presenter right, text left."
    )
    assert card["editable_image_prompt"] == "Presenter right, text left."
    assert card["generate_now"]["button_label"] == "Generate Now"
    assert "DO THIS FIRST" in card["generate_now"]["final_prompt_preview"]
    assert "Chair Exercise" in card["generate_now"]["final_prompt_preview"]

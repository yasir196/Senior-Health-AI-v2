from Thumbnail_Pipeline.dashboard.loser_actions import loser_repair_card

def test_loser_card_autobuilds_full_edit_prompt_and_source_image():
    card=loser_repair_card(audit_id=7,title="Immutable title",original_text="OLD TEXT",source_thumbnail_path="Analytics/youtube_assets/a/thumbnails/old.jpg",why=[{"feature":"clutter","reason":"higher in lower CTR group"}],suggestion={"same_category_winner_evidence":[{"title":"W","thumbnail_text":"WIN TEXT","ctr":8.1,"impressions":12000}]} ,proposed_text="NEW TEXT")
    assert "TASK: EDIT THE EXISTING LOSER THUMBNAIL" in card["generated_edit_prompt_original"]
    assert card["source_thumbnail_path"].endswith("old.jpg")
    assert "SOURCE THUMBNAIL TO EDIT" in card["generate_now"]["final_prompt_preview"]
    assert "NEW TEXT" in card["generate_now"]["final_prompt_preview"]

def test_human_prompt_is_sent_exactly_as_visible_override():
    custom="MY HUMAN EDIT PROMPT -- KEEP EXACTLY"
    card=loser_repair_card(audit_id=8,title="T",original_text="OLD",source_thumbnail_path="x.jpg",why=[],suggestion={},proposed_text="NEW",human_prompt_override=custom)
    assert card["editable_image_prompt"]==custom
    assert custom in card["generate_now"]["final_prompt_preview"]
    assert card["prompt_human_edited"] is True

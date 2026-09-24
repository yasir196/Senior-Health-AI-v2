from Thumbnail_Pipeline.intelligence.title_text_pair import pair_features,summarize_title_text_pairs

def test_title_thumbnail_pair_detects_overlap_and_new_tokens():
    p=pair_features("Swollen Legs at Night? Try These Bed Movements","ONE LEG OR BOTH?")
    assert "leg" in p["new_thumbnail_tokens"]
    assert p["thumbnail_adds_new_tokens"] is True

def test_pair_summary_has_no_seeded_hook_taxonomy():
    s=summarize_title_text_pairs([{"performance":{"title":"T","ctr":5,"impressions":1000},"ocr":{"text":"WHAT HAPPENS NEXT?"}}])
    assert s["method"]=="neutral_title_text_overlap_no_seeded_hook_vocabulary"
    assert "hook_type" not in s["pairs"][0]

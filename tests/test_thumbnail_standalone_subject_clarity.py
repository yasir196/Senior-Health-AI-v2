from pathlib import Path


AGENT = Path(__file__).resolve().parents[1] / "Agents" / "Thumbnail_Agent.md"


def test_winner_selection_requires_standalone_subject_clarity():
    text = AGENT.read_text(encoding="utf-8")

    assert "Standalone Subject Clarity Test" in text
    assert "Hide the video title" in text
    assert "overlay plus the dominant viewer-facing visual" in text
    assert "core subject or unmistakable subject category immediately identifiable" in text
    assert "Complementary` means withholding a different answer or angle, not hiding what the video is about" in text


def test_generic_food_loses_to_specific_subject_when_visual_is_ambiguous():
    text = AGENT.read_text(encoding="utf-8")

    generic = text.index("`THE FOOD` is weaker")
    specific = text.index("than `PEANUT BUTTER`")
    assert generic < specific
    assert "unlabeled jar/spoon" in text
    assert "semantic comparison rule, not a fixed food-keyword list" in text
    assert "reject a generic placeholder winner" in text

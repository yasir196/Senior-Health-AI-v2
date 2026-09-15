from pathlib import Path

AGENT = Path(__file__).resolve().parents[1] / "Agents" / "Thumbnail_Agent.md"


def text():
    return AGENT.read_text(encoding="utf-8")


def test_no_four_word_hard_limit():
    t = text()
    assert "Thumbnail text must be 4 words or fewer" not in t
    assert "There is no fixed thumbnail word-count maximum" in t


def test_senior_clarity_is_explicit_gate():
    t = text()
    assert "Senior-Audience Comprehension Lock" in t
    assert "Thumbnail-Only Senior Clarity Test" in t
    assert "Senior Comprehension / Semantic Completeness < 7/10" in t


def test_title_is_not_required_for_thumbnail_understanding():
    t = text()
    assert "thumbnail may be the viewer's primary read" in t
    assert "hide the video title" in t.lower()


def test_longer_copy_is_allowed_when_readable():
    t = text()
    assert "Longer text is allowed" in t
    assert "Do not assume fewer words produce higher CTR" in t
    assert "minimum interpretation effort, not minimum word count" in t


def test_length_can_be_learned_not_invented():
    t = text()
    assert "text length as a packaging variable to be learned from channel evidence" in t
    assert "never invent a length preference" in t

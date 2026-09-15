from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_thumbnail_agent_has_renderability_gate():
    text = (ROOT / "Agents" / "Thumbnail_Agent.md").read_text(encoding="utf-8")
    assert "Instant Visual Comprehension / Renderability Test" in text
    assert "Prompt Translation Test" in text
    assert "Instant Visual Comprehension < 7/10" in text
    assert "one-second cold-viewer test" in text
    assert "prompt prose cannot rescue a confusing concept" in text

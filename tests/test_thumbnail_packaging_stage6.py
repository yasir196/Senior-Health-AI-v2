from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def _thumbnail_command_source():
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    start = src.index('"Thumbnail": f"')
    end = src.index('\n        "Script Outline"', start)
    return src[start:end]

def test_stage6_thumbnail_command_injects_active_packaging_artifact():
    src = _thumbnail_command_source()
    assert "Analytics/active_channel_packaging_rules.md" in src
    assert "only the ACTIVE rules artifact may be injected" in src
    assert "immutable title promise" in src
    assert "Medical Gate requirements" in src

def test_stage6_thumbnail_agent_has_context_and_safety_precedence():
    text = (ROOT / "Agents" / "Thumbnail_Agent.md").read_text(encoding="utf-8")
    assert "ACTIVE CHANNEL PACKAGING GUIDANCE — STAGE 6" in text
    assert "Apply **only ACTIVE**" in text
    assert "historical **association**" in text
    assert "If not applicable, treat it as N/A" in text
    assert "must **never override** the immutable user-supplied Anchor/Outlier Title" in text
    assert "CANDIDATE, REJECTED, or RETIRED" in text
    assert "injection boundary" in text

def test_stage6_does_not_change_stable_frozen_thumbnail_agent():
    stable = ROOT / "Agents" / "Stable" / "Thumbnail_Agent_v1.0.md"
    assert stable.exists()
    assert "ACTIVE CHANNEL PACKAGING GUIDANCE — STAGE 6" not in stable.read_text(encoding="utf-8")

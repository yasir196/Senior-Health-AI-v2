from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_medical_gate_bounds_verified_context_before_rejecting():
    text = (ROOT / "Agents" / "Medical_Agent.md").read_text(encoding="utf-8")
    assert "Bound-before-reject rule" in text
    assert "CONTEXT-ONLY / LIMITATION-ONLY" in text
    assert "Do not reject an entire verified evidence module solely because it cannot prove the video's strongest outcome claim." in text
    assert "Association must remain association" in text
    assert "mechanism must not be presented as a demonstrated clinical outcome" in text


def test_research_normalizes_narrow_verified_context_for_gate1():
    text = (ROOT / "Agents" / "Research_Agent.md").read_text(encoding="utf-8")
    assert "normalize the narrowest source-supported proposition as its own material claim" in text
    assert "bounded/context-only" in text
    assert "Never manufacture a weaker claim that the source itself does not support." in text


def test_imported_research_command_preserves_bounded_context_lane():
    text = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "Gate 1 must apply its bound-before-reject rule" in text
    assert "inability to prove the strongest target outcome is not by itself a reason" in text
    assert "preserving population, formulation, study-design, and non-transfer limits" in text

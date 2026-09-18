from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "Templates" / "Writing" / "opus_writer_prompt.md"
APP = ROOT / "app.py"


def test_writer_template_requires_legitimate_depth_without_runtime_padding():
    text = TEMPLATE.read_text(encoding="utf-8")

    assert "## Full Evidence Development Lock" in text
    assert "Do not treat the anti-padding" in text
    assert "Fully develop every materially useful approved evidence module" in text
    assert "Depth is not padding." in text
    assert "what was studied" in text
    assert "what the evidence means" in text
    assert "what it does not mean" in text
    assert "practical viewer consequence" in text
    assert "Do not compress an approved module merely for brevity." in text
    assert "Runtime remains advisory metadata after drafting" in text


def test_prepare_opus_package_preserves_depth_lock_and_gate1_authority():
    text = APP.read_text(encoding="utf-8")

    assert "copy the complete `## Full Evidence Development Lock`" in text
    assert "fully develop every materially useful approved evidence module" in text
    assert "rather than summarize or compress it for brevity" in text
    assert "never reviving unapproved material from research or the outline" in text
    assert "legitimate depth, not padding" in text
    assert "Runtime Advisory: ADVISORY ONLY — NON-BLOCKING" in text

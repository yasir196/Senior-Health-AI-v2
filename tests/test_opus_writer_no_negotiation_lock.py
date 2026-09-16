from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_writer_prompt_has_no_negotiation_lock():
    text=(ROOT / "Templates/Writing/opus_writer_prompt.md").read_text(encoding="utf-8")
    assert "## Execution / No-Negotiation Lock" in text
    assert "Do not pre-negotiate the assignment" in text
    assert "Runtime and word count cannot influence drafting" in text
    assert "Runtime is ADVISORY ONLY — NON-BLOCKING" in text
    assert "Only after `06_final_script.md` is complete" in text
    assert "do not withhold, shorten, pad, or refuse" in text

def test_package_generator_preserves_no_negotiation_lock():
    text=(ROOT / "app.py").read_text(encoding="utf-8")
    assert "`## Execution / No-Negotiation Lock`" in text
    assert "draft first without pre-negotiating" in text

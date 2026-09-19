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



def test_writer_module_completion_is_not_first_correct_coverage():
    text = TEMPLATE.read_text(encoding="utf-8")

    assert "## Full Evidence Development Lock" in text
    assert "Module-completion rule" in text
    assert "NOT complete merely because its claim and boundary have each been stated once" in text
    assert "First correct coverage is the minimum for inclusion, not the completion criterion." in text
    assert "Silent pre-finalization evidence-depth audit" in text
    assert "unused supported explanatory dimension" in text
    assert "do not remove new interpretation, distinctions, limitations, or consequences" in text
    assert "Do not report this audit in the narration or use it to chase a runtime/word-count target." in text


def test_prepare_opus_package_preserves_operational_module_completion_rule():
    text = APP.read_text(encoding="utf-8")

    assert "First correct coverage of a claim plus its boundary is the minimum for inclusion, NOT the completion criterion." in text
    assert "study/population/formulation context" in text
    assert "null/mixed/uncertain-result meaning" in text
    assert "state it once and move on" in text
    assert "silent pre-finalization evidence-depth audit" in text

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_retention_analyzer_requires_rule_by_rule_compliance():
    text = (ROOT / "Templates/Writing/retention_structure_analyzer.md").read_text(encoding="utf-8")
    assert "ACTIVE CHANNEL RULE COMPLIANCE" in text
    assert "Evaluate EACH currently ACTIVE rule" in text
    assert "Script Evidence (5–8+ word verbatim anchor)" in text
    assert "Corrective Patch ID(s)" in text
    assert "do not merely confirm that the rule was injected" in text


def test_narrative_qa_requires_downstream_final_rule_verification():
    agent = (ROOT / "Agents/Narrative_QA_Agent.md").read_text(encoding="utf-8")
    template = (ROOT / "Templates/Writing/narrative_qa_output_template.md").read_text(encoding="utf-8")
    opus = (ROOT / "Templates/Writing/opus_narrative_qa.md").read_text(encoding="utf-8")
    assert "FINAL ACTIVE-RULE VERIFICATION" in agent
    assert "## Active Channel Rule Compliance" in template
    assert "Final Script Evidence (5–8+ word verbatim anchor)" in template
    assert "Verify EACH currently ACTIVE rule" in opus


def test_app_commands_request_actual_script_compliance_not_just_injection():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "verify EACH currently ACTIVE rule against the actual current 06_final_script.md" in app
    assert "Do not count rule injection into the writer package as implementation evidence" in app
    assert "do not treat writer-package injection or the earlier Retention report as proof of implementation" in app

from pathlib import Path

from v31_core import validate_qa_report_sections

ROOT = Path(__file__).resolve().parents[1]


def test_narrative_qa_pass_does_not_require_removed_active_channel_section():
    report = """# 14 Narrative QA

Status: PASS

## Semantic Progression Gate

| Beat | Approved source trace |
|---|---|
| Example | C01 |

## Approved Blueprint Order Audit

| Expected | Current | Status |
|---|---|---|
| Hook | Hook | PASS |
"""
    ok, issues = validate_qa_report_sections("Narrative QA", report)

    assert ok
    assert issues == []


def test_narrative_qa_still_requires_current_audit_sections():
    report = """# 14 Narrative QA

Status: PASS

## Semantic Progression Gate

| Beat | Approved source trace |
|---|---|
| Example | C01 |
"""
    ok, issues = validate_qa_report_sections("Narrative QA", report)

    assert not ok
    assert "missing required section: Approved Blueprint Order Audit" in issues


def test_active_channel_rule_output_is_silent_in_current_narrative_prompts():
    agent = (ROOT / "Agents/Narrative_QA_Agent.md").read_text(encoding="utf-8")
    opus = (ROOT / "Templates/Writing/opus_narrative_qa.md").read_text(encoding="utf-8")

    assert "Active Channel Rule Compliance" not in agent
    assert "Active Channel Rule Compliance" not in opus
    assert "No ACTIVE channel script rules" not in agent
    assert "No ACTIVE channel script rules" not in opus

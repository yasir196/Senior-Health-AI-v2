from pathlib import Path

from v31_core import get_gate_status, validate_qa_report_sections


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _valid_narrative_report() -> str:
    return """# 14 Narrative QA

Status: PASS

## Semantic Progression Gate

| Beat / idea | Classification | Approved source trace | Action |
|---|---|---|---|
| Hook | NEW | 05_script_outline.md — Hook | KEEP |

## Approved Blueprint Order Audit

| Expected order | Current order | Authorization/source | Status |
|---|---|---|---|
| Hook > Introduction > Main > Conclusion | same | 05_script_outline.md | PASS |

## Active Channel Rule Compliance

| Active Rule | Status | Evidence |
|---|---|---|
| Rule 1 | PASS | example anchor |
"""


def _valid_voice_checklist() -> str:
    return """# 06b Voice Checklist

## Speech QA
- starts with hook: PASS

## Paragraph Statistics
- total paragraphs: 12

## Pronunciation Review
- calcium

## Chapter Plan
- Hook

## Upload Checklist
- upload complete file
"""


def test_narrative_bare_pass_is_rejected(tmp_path: Path) -> None:
    _write(tmp_path / "14_narrative_qa.md", "Status: PASS\n")
    result = get_gate_status(tmp_path, "Narrative QA", {})
    assert result.status == "FAIL"
    assert "Semantic Progression Gate" in result.reason
    assert "Approved Blueprint Order Audit" in result.reason
    assert "Active Channel Rule Compliance" in result.reason


def test_narrative_pass_requires_source_trace_column(tmp_path: Path) -> None:
    text = _valid_narrative_report().replace(" | Approved source trace", "")
    _write(tmp_path / "14_narrative_qa.md", text)
    result = get_gate_status(tmp_path, "Narrative QA", {})
    assert result.status == "FAIL"
    assert "APPROVED SOURCE TRACE" in result.reason


def test_complete_narrative_pass_is_accepted(tmp_path: Path) -> None:
    _write(tmp_path / "14_narrative_qa.md", _valid_narrative_report())
    result = get_gate_status(tmp_path, "Narrative QA", {})
    assert result.status == "PASS"


def test_voice_checklist_without_status_passes_when_complete(tmp_path: Path) -> None:
    _write(tmp_path / "06b_voice_checklist.md", _valid_voice_checklist())
    result = get_gate_status(tmp_path, "Speech Optimizer", {})
    assert result.status == "PASS"


def test_voice_checklist_missing_required_section_fails(tmp_path: Path) -> None:
    text = _valid_voice_checklist().replace("## Pronunciation Review\n- calcium\n\n", "")
    _write(tmp_path / "06b_voice_checklist.md", text)
    result = get_gate_status(tmp_path, "Speech Optimizer", {})
    assert result.status == "FAIL"
    assert "Pronunciation Review" in result.reason


def test_medical_gate_2_accepts_verdict_below_status_heading(tmp_path: Path) -> None:
    _write(
        tmp_path / "15_medical_gate_2.md",
        "# Medical Agent Gate 2\n\n## Status\n\nPASS WITH REVISIONS\n",
    )
    result = get_gate_status(tmp_path, "Medical Gate 2", {})
    assert result.status == "PASS WITH REVISIONS"


def test_status_heading_parser_preserves_exact_pass(tmp_path: Path) -> None:
    _write(
        tmp_path / "15_medical_gate_2.md",
        "# Medical Agent Gate 2\n\n### Status\nPASS\n",
    )
    result = get_gate_status(tmp_path, "Medical Gate 2", {})
    assert result.status == "PASS"


def test_validator_is_scoped_to_supported_artifacts() -> None:
    ok, issues = validate_qa_report_sections("Medical Gate 2", "Status: PASS\n")
    assert ok is True
    assert issues == []


def test_speech_optimizer_prompt_no_longer_bypasses_gates() -> None:
    app_text = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert "run the Speech Optimizer only after Narrative QA and Medical Gate 2 both report exactly PASS" in app_text
    assert "Do NOT check or require Narrative QA, Medical Gate 2" not in app_text

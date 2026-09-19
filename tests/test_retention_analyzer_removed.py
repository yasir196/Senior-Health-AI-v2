from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_retention_structure_analyzer_is_not_an_active_workflow_stage():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    core = (ROOT / "v31_core.py").read_text(encoding="utf-8")

    forbidden = (
        "Retention Structure Analysis",
        "Retention Structure Analyzer",
        "retention_structure_analysis.md",
        "retention_structure_ready",
        "retention_revision_applied",
    )
    for token in forbidden:
        assert token not in app
        assert token not in core


def test_narrative_workflow_has_no_retention_analyzer_dependency():
    paths = (
        ROOT / "Agents" / "Narrative_QA_Agent.md",
        ROOT / "Templates" / "Writing" / "opus_narrative_qa.md",
        ROOT / "Templates" / "Writing" / "opus_writer_prompt.md",
    )
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "Retention Structure Analyzer" not in text
        assert "Retention Structure Analysis" not in text
        assert "retention_structure_analysis.md" not in text


def test_retention_analyzer_template_is_removed():
    assert not (ROOT / "Templates" / "Writing" / "retention_structure_analyzer.md").exists()


def test_opus_writer_has_no_forced_retention_lock_or_report():
    writer = (ROOT / "Templates" / "Writing" / "opus_writer_prompt.md").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")

    forbidden = (
        "## Retention-First Drafting Lock",
        "retention-prevention pass",
        "06_retention_report.md",
    )
    for token in forbidden:
        assert token not in writer
        assert token not in app

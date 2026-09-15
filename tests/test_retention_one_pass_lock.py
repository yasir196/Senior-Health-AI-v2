from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/"app.py").read_text(encoding="utf-8")
CORE=(ROOT/"v31_core.py").read_text(encoding="utf-8")
PROMPT=(ROOT/"Templates/Writing/retention_structure_analyzer.md").read_text(encoding="utf-8")

def test_prompt_locks_one_pass():
    assert "12. ONE-PASS RETENTION LOCK:" in PROMPT
    assert "must advance to Narrative QA" in PROMPT
    assert "Never use a later retention pass to reverse" in PROMPT

def test_ui_disables_second_analysis_once_report_exists():
    assert "and not report_path.is_file()" in APP
    assert "Do not run Retention Analysis again." in APP
    assert "Retention Complete — Continue to Narrative QA" in APP

def test_old_rerun_instruction_removed():
    assert "then rerun this analyzer" not in APP
    assert "without re-running Retention Analysis" in APP

def test_completion_detects_revised_script_after_report():
    assert "def _retention_revision_applied(project: Path) -> bool:" in APP
    assert "script_path.stat().st_mtime > report_path.stat().st_mtime" in APP

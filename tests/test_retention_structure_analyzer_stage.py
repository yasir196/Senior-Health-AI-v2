from pathlib import Path
from v31_core import WORKFLOW_STAGES, retention_structure_ready


def _config():
    return {
        "writer_minimum_words": 1,
        "writer_required_headings": ["Hook", "Introduction", "Main Content", "Conclusion"],
        "target_runtime_minutes": 25,
        "target_runtime_range_minutes": [1, 100],
        "narration_words_per_minute": 169,
    }


def test_retention_structure_stage_is_available_and_final_script_path_is_unchanged(tmp_path: Path):
    assert "Retention Structure Analysis" in WORKFLOW_STAGES
    script = tmp_path / "06_final_script.md"
    script.write_text("# Hook\nHook words.\n# Introduction\nIntro words.\n# Main Content\nMain words.\n# Conclusion\nConclusion words. Talk with your healthcare professional if needed. Subscribe for more evidence-based videos.", encoding="utf-8")
    ready, reasons = retention_structure_ready(tmp_path, _config())
    assert ready, reasons
    assert script.is_file()


def test_locked_template_contains_required_guardrails():
    template = Path("Templates/Writing/retention_structure_analyzer.md").read_text(encoding="utf-8")
    for required in (
        "Retention Risk Reason:", "RE-HOOKS ARE ADAPTIVE, NOT TIMED",
        "H## (hook), O## (order), P## (pacing)", "5–8+ exact words",
        "ORDER → HOOK → PACING → REPETITION → CAUTION PACING → BRIDGES",
        "SCRIPT CHAT REVISION PROMPT", "Facts changed: NO", "Winning title changed: NO",
    ):
        assert required in template


def test_app_wiring_is_non_destructive_and_uses_locked_output():
    app = Path("app.py").read_text(encoding="utf-8")
    assert '"Retention Structure Analysis": f"For {ref}, run ONLY the Retention Structure Analyzer.' in app
    assert "Create or replace ONLY retention_structure_analysis.md in the selected project root" in app
    assert "do not modify 06_final_script.md" in app
    assert '"Retention Structure Analysis": render_retention_structure_analysis' in app


from pathlib import Path

def test_archive_runs_before_chapter_finalizer_and_has_separate_error_boundary():
    text = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    block = text[text.index("if result.returncode == 0 and is_seo_run:"):text.index("    return result", text.index("if result.returncode == 0 and is_seo_run:"))]
    assert block.index("archive_production_learning_checkpoint") < block.index("finalize_project_seo(project)")
    assert "Production learning archive: FAIL" in block
    assert "SEO chapter finalization: FAIL" in block

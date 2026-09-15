
from pathlib import Path

def test_seo_archive_trigger_is_bound_to_selected_stage_not_prompt_text():
    text = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert 'is_seo_run = stage == "SEO"' in text
    assert 'stage=stage' in text


from pathlib import Path

def test_retention_mapping_shows_exact_project_assets_path():
    text = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert 'st.markdown("##### Retention mapping source")' in text
    assert 'ANALYTICS_DIR / "project_assets" / str(retention_id)' in text
    assert 'st.code(str(project_assets_dir.resolve()), language=None)' in text
    assert 'Project assets folder: FOUND' in text
    assert 'Project assets folder: MISSING' in text

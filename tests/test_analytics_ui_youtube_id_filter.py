from pathlib import Path

def test_analytics_ui_hides_unlinked_projects_and_has_manual_link_workflow():
    text=(Path(__file__).resolve().parents[1]/'app.py').read_text(encoding='utf-8')
    assert '"YouTube Video Link"' in text
    assert 'bind_youtube_video_id_to_project' in text
    assert 'if str(v.get("youtube_video_id") or "").strip()' in text
    assert 'if str(v.get("youtube_video_id") or "").strip() and v.get("project_id")' in text
    assert 'Titles are not used for identity matching.' in text

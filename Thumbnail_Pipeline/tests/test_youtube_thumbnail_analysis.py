from Thumbnail_Pipeline.adapters.youtube_thumbnail_analysis import analyze_youtube_reference_thumbnail, clear_youtube_reference_thumbnails

def test_missing_public_url_is_explicit():
    r=analyze_youtube_reference_thumbnail({"video_id":"x","thumbnail_url_or_path":None},project="test-project")
    assert r["thumbnail_analysis_status"]=="unavailable"

def test_untrusted_thumbnail_host_is_rejected():
    r=analyze_youtube_reference_thumbnail({"video_id":"x","thumbnail_url_or_path":"https://example.com/x.jpg"},project="test-project")
    assert r["thumbnail_analysis_status"]=="unavailable"
    assert r["thumbnail_analysis_reason"]=="untrusted_thumbnail_url"


def test_clear_reference_thumbnails_removes_only_current_project_images(monkeypatch,tmp_path):
    import Thumbnail_Pipeline.adapters.youtube_thumbnail_analysis as mod
    monkeypatch.setattr(mod,"safe_output",lambda p: tmp_path / p)
    current=tmp_path/"fresh-project"; current.mkdir()
    other=tmp_path/"other-project"; other.mkdir()
    (current/"old.jpg").write_bytes(b"x")
    (current/"keep.json").write_text("{}",encoding="utf-8")
    (other/"other.jpg").write_bytes(b"x")
    result=clear_youtube_reference_thumbnails("fresh-project")
    assert result["removed_thumbnail_files"]==1
    assert not (current/"old.jpg").exists()
    assert (current/"keep.json").exists()
    assert (other/"other.jpg").exists()

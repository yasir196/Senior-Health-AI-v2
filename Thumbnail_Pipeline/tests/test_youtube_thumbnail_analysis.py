from Thumbnail_Pipeline.adapters.youtube_thumbnail_analysis import analyze_youtube_reference_thumbnail

def test_missing_public_url_is_explicit():
    r=analyze_youtube_reference_thumbnail({"video_id":"x","thumbnail_url_or_path":None})
    assert r["thumbnail_analysis_status"]=="unavailable"

def test_untrusted_thumbnail_host_is_rejected():
    r=analyze_youtube_reference_thumbnail({"video_id":"x","thumbnail_url_or_path":"https://example.com/x.jpg"})
    assert r["thumbnail_analysis_status"]=="unavailable"
    assert r["thumbnail_analysis_reason"]=="untrusted_thumbnail_url"

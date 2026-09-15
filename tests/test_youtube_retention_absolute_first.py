from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_retention_absolute_metric_is_queried_independently():
    text = (ROOT / 'youtube_api_sync.py').read_text(encoding='utf-8')
    assert 'metrics="audienceWatchRatio"' in text
    assert 'metrics="audienceWatchRatio,relativeRetentionPerformance"' not in text
    assert 'metrics="relativeRetentionPerformance"' in text


def test_retention_unavailable_is_diagnosed_not_silent():
    text = (ROOT / 'youtube_api_sync.py').read_text(encoding='utf-8')
    assert '"retention_unavailable": 0' in text
    assert '"retention_diagnostics": []' in text
    assert 'YouTube Analytics API returned {len(retention_rows)} absolute retention row(s); curve not stored.' in text


def test_ui_exposes_retention_sync_diagnostics():
    text = (ROOT / 'app.py').read_text(encoding='utf-8')
    assert 'Retention sync diagnostics' in text
    assert 'Retention unavailable/skipped for' in text

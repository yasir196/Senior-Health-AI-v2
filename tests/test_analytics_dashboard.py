from pathlib import Path
import pandas as pd

from analytics_db import init_db, bulk_import_channel_content_csv, channel_dashboard_data

def test_dashboard_reads_latest_performance(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    init_db(db)
    df = pd.DataFrame([{
        "Content": "MAnJlungV9M",
        "Video title": "Test Video",
        "Video publish time": "Aug 5, 2026",
        "Views": 1000,
        "Watch time (hours)": 100,
        "Average view duration": "6:00",
        "Average percentage viewed (%)": 30,
        "Thumbnail impressions": 10000,
        "Thumbnail click-through rate (%)": 7.5,
        "Subscribers": 10,
    }])
    bulk_import_channel_content_csv(db, df)
    data = channel_dashboard_data(db)
    assert data["summary"]["videos_with_analytics"] == 1
    assert data["summary"]["total_views"] == 1000
    assert round(data["summary"]["avg_ctr"], 2) == 7.50
    assert round(data["summary"]["avg_apv"], 2) == 30.00

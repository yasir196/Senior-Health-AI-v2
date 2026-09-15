from pathlib import Path
import pandas as pd

from analytics_db import init_db, bulk_import_channel_content_csv, list_videos

def test_weekday_saved_at_import(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    init_db(db)
    df = pd.DataFrame([{
        "Content": "MAnJlungV9M",
        "Video title": "Test Video",
        "Video publish time": "Aug 5, 2026",
        "Views": 100,
        "Average view duration": "5:00",
        "Average percentage viewed (%)": 30,
        "Impressions": 1000,
        "Impressions click-through rate (%)": 6.0,
    }])
    bulk_import_channel_content_csv(db, df)
    video = list_videos(db)[0]
    assert video["publish_date"] == "2026-08-05"
    assert video["publish_weekday"] == "Wednesday"

from pathlib import Path
import pandas as pd
from analytics_db import init_db, bulk_import_channel_content_csv, list_videos, weekday_performance_summary

def test_publish_date_saved(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    init_db(db)
    df = pd.DataFrame([{
        "Content": "MAnJlungV9M",
        "Video title": "Peanut Butter",
        "Video publish time": "Aug 5, 2026",
        "Views": 1000,
        "Average view duration": "6:21",
        "Average percentage viewed (%)": 26.41,
        "Impressions": 10000,
        "Impressions click-through rate (%)": 7.01,
    }])
    bulk_import_channel_content_csv(db, df)
    assert list_videos(db)[0]["publish_date"] == "2026-08-05"

def test_weekday_summary(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    init_db(db)
    df = pd.DataFrame([
        {"Content":"MAnJlungV9M","Video title":"A","Video publish time":"Aug 5, 2026","Views":1000,"Average view duration":"6:00","Average percentage viewed (%)":30,"Impressions":10000,"Impressions click-through rate (%)":7},
        {"Content":"gjCGV0Ia4Qg","Video title":"B","Video publish time":"Aug 12, 2026","Views":800,"Average view duration":"5:00","Average percentage viewed (%)":25,"Impressions":9000,"Impressions click-through rate (%)":6},
    ])
    bulk_import_channel_content_csv(db, df)
    s = weekday_performance_summary(db)
    assert len(s) == 1
    assert s.iloc[0]["weekday"] == "Wednesday"
    assert int(s.iloc[0]["videos"]) == 2

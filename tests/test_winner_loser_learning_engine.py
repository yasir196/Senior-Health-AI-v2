from pathlib import Path
import pandas as pd
from analytics_db import init_db, bulk_import_channel_content_csv, winner_loser_learning_data

def test_learning_engine_classifies_channel_relative(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    init_db(db)
    rows = [
        ("AAAAA111111", "Strong", 8.0, 40.0),
        ("BBBBB222222", "Packaging", 2.0, 35.0),
        ("CCCCC333333", "Hold", 7.0, 15.0),
        ("DDDDD444444", "Both", 1.0, 10.0),
    ]
    df = pd.DataFrame([{
        "Content": vid,
        "Video title": title,
        "Video publish time": "Aug 5, 2026",
        "Views": 100,
        "Average view duration": "5:00",
        "Average percentage viewed (%)": apv,
        "Thumbnail impressions": 1000,
        "Thumbnail click-through rate (%)": ctr,
    } for vid, title, ctr, apv in rows])
    bulk_import_channel_content_csv(db, df)
    data = winner_loser_learning_data(db)
    got = dict(zip(data["videos"]["title"], data["videos"]["diagnosis"]))
    assert got["Strong"] == "STRONG"
    assert got["Packaging"] == "PACKAGING OPPORTUNITY"
    assert got["Hold"] == "CONTENT HOLD OPPORTUNITY"
    assert got["Both"] == "PACKAGING + CONTENT"

from pathlib import Path
import pandas as pd
from analytics_db import init_db, bulk_import_channel_content_csv, winner_loser_learning_data

def test_early_signal_excluded_and_patterns_generated(tmp_path: Path):
    db = tmp_path/"db.sqlite"
    init_db(db)
    rows = [
        ("AAAAA111111","Over 60? Strong One",200,2000,8.0,40.0),
        ("BBBBB222222","Over 60? Strong Two",150,1800,7.0,35.0),
        ("CCCCC333333","Weak Packaging",120,1500,2.0,36.0),
        ("DDDDD444444","Low Data Strong",5,50,9.0,60.0),
    ]
    df = pd.DataFrame([{
        "Content": vid, "Video title": title, "Video publish time":"Aug 5, 2026",
        "Views": views, "Average view duration":"5:00",
        "Average percentage viewed (%)": apv,
        "Thumbnail impressions": imp,
        "Thumbnail click-through rate (%)": ctr,
    } for vid,title,views,imp,ctr,apv in rows])
    bulk_import_channel_content_csv(db, df)
    data = winner_loser_learning_data(db)
    videos = data["videos"].set_index("title")
    assert videos.loc["Low Data Strong","diagnosis"] == "EARLY SIGNAL"
    assert data["summary"]["early_signal"] == 1
    assert data["summary"]["videos_learning_eligible"] == 3
    assert "After/Over age framing" in set(data["patterns"]["Pattern"])

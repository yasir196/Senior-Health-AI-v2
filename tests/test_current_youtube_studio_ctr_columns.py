from pathlib import Path
import sqlite3
import pandas as pd
from analytics_db import init_db, bulk_import_channel_content_csv, list_videos

def test_thumbnail_ctr_and_impressions_import(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    init_db(db)
    df = pd.DataFrame([{
        "Content": "gjCGV0Ia4Qg",
        "Video title": "Over 60? Drink This for Better Leg Blood Flow",
        "Video publish time": "Aug 16, 2026",
        "Views": 364,
        "Watch time (hours)": 27.0644,
        "Average view duration": "0:04:27",
        "Average percentage viewed (%)": 20.2,
        "Subscribers": 7,
        "Thumbnail impressions": 4662,
        "Thumbnail click-through rate (%)": 4.63,
    }])
    result = bulk_import_channel_content_csv(db, df, source_file="Table data.csv")
    assert result["imported_videos"] == 1
    aid = list_videos(db)[0]["analytics_id"]

    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    row = con.execute(
        "SELECT * FROM performance_snapshots WHERE analytics_id=? ORDER BY id DESC LIMIT 1",
        (aid,)
    ).fetchone()
    con.close()

    assert row is not None
    assert float(row["ctr_percent"]) == 4.63
    assert int(row["impressions"]) == 4662

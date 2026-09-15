from pathlib import Path
import pandas as pd

from analytics_db import (
    init_db, bulk_import_channel_content_csv, bulk_import_channel_traffic_csv,
    list_videos, latest_performance, traffic_source_df
)


def test_bulk_content_creates_and_updates_video_records(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    init_db(db)
    df = pd.DataFrame([
        {
            "Video ID": "aaa111bbb22",
            "Video title": "Video One",
            "Views": 1000,
            "Watch time (hours)": 100,
            "Average view duration": "6:00",
            "Average percentage viewed (%)": 35,
            "Impressions": 10000,
            "Impressions click-through rate (%)": 7.5,
            "Subscribers": 10,
        },
        {
            "Video ID": "ccc333ddd44",
            "Video title": "Video Two",
            "Views": 500,
            "Watch time (hours)": 40,
            "Average view duration": "4:30",
            "Average percentage viewed (%)": 25,
            "Impressions": 8000,
            "Impressions click-through rate (%)": 4.2,
            "Subscribers": 3,
        },
    ])
    res = bulk_import_channel_content_csv(db, df, source_file="content.csv")
    assert res["imported_videos"] == 2
    videos = list_videos(db)
    assert len(videos) == 2
    ids = {v["youtube_video_id"] for v in videos}
    assert ids == {"aaa111bbb22", "ccc333ddd44"}


def test_bulk_traffic_groups_by_video_id(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    init_db(db)
    content = pd.DataFrame([{
        "Video ID": "aaa111bbb22",
        "Video title": "Video One",
        "Views": 1000,
        "Average view duration": "6:00",
        "Average percentage viewed (%)": 35,
        "Impressions": 10000,
        "Impressions click-through rate (%)": 7.5,
    }])
    bulk_import_channel_content_csv(db, content)
    traffic = pd.DataFrame([
        {"Video ID":"aaa111bbb22","Video title":"Video One","Traffic source":"Suggested videos","Views":700,"Average view duration":"6:20","Average percentage viewed (%)":37,"Impressions":7000,"Impressions click-through rate (%)":7.0},
        {"Video ID":"aaa111bbb22","Video title":"Video One","Traffic source":"Browse features","Views":250,"Average view duration":"5:30","Average percentage viewed (%)":30,"Impressions":2500,"Impressions click-through rate (%)":8.0},
    ])
    res = bulk_import_channel_traffic_csv(db, traffic)
    assert res["imported_videos"] == 1
    assert res["imported_rows"] == 2
    aid = list_videos(db)[0]["analytics_id"]
    df = traffic_source_df(db, aid)
    assert set(df["traffic_source"]) == {"Suggested videos", "Browse features"}

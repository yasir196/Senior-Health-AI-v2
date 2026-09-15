import json
from pathlib import Path

import pandas as pd

from analytics_db import (
    init_db, ensure_project_record, list_videos, snapshot_timestamped_transcript,
    scene_snapshot_df, import_youtube_csv, register_youtube_only_video
)


def test_project_record_survives_project_deletion(tmp_path: Path):
    db = tmp_path / "Analytics" / "db.sqlite"
    project = tmp_path / "Projects" / "demo"
    project.mkdir(parents=True)
    (project / "project.json").write_text(json.dumps({
        "project_id": "p1", "anchor_title": "My Video", "created_at": "2026-01-01T00:00:00"
    }), encoding="utf-8")
    aid = ensure_project_record(db, project)
    assert aid
    project.rename(tmp_path / "deleted_demo")
    videos = list_videos(db)
    assert videos[0]["locked_title"] == "My Video"


def test_timestamped_transcript_fallback(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    init_db(db)
    aid = register_youtube_only_video(db, title="Old Video")
    count = snapshot_timestamped_transcript(
        db, aid,
        "[00:00:00] hello world\n[00:00:03] next point\n[00:00:07] third point"
    )
    assert count == 3
    df = scene_snapshot_df(db, aid)
    assert list(df["scene_id"]) == ["TS0001", "TS0002", "TS0003"]
    assert set(df["source"]) == {"transcript_reconstructed"}


def test_performance_youtube_headers(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    aid = register_youtube_only_video(db, title="Video")
    df = pd.DataFrame([{
        "Content": "Total",
        "Views": 2955,
        "Engaged views": 2954,
        "Watch time (hours)": 313.4036,
        "Average view duration": "6:21",
        "Average percentage viewed (%)": "26.41",
        "Impressions": 26660,
        "Impressions click-through rate (%)": "7.01",
        "Subscribers": 26,
        "Unique viewers": 2449,
    }])
    result = import_youtube_csv(db, aid, df, source_file="Table data.csv")
    assert result["kind"] == "performance"
    assert result["average_view_duration_seconds"] == 381
    assert result["average_percentage_viewed"] == 26.41
    assert result["ctr_percent"] == 7.01


def test_traffic_source_import(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    aid = register_youtube_only_video(db, title="Video")
    df = pd.DataFrame([
        {"Traffic source": "Suggested videos", "Views": 3216, "Average view duration": "6:51", "Average percentage viewed (%)": 28.75, "Impressions": 10000, "Impressions click-through rate (%)": 6.52},
        {"Traffic source": "Browse features", "Views": 1155, "Average view duration": "5:20", "Average percentage viewed (%)": 22.1, "Impressions": 5000, "Impressions click-through rate (%)": 7.2},
    ])
    result = import_youtube_csv(db, aid, df, source_file="Traffic.csv")
    assert result["kind"] == "traffic_source"
    assert result["rows"] == 2


def test_existing_youtube_only_exact_title_is_not_auto_linked(tmp_path: Path):
    from analytics_db import auto_link_existing_projects
    db = tmp_path / 'Analytics' / 'db.sqlite'
    projects = tmp_path / 'Projects'
    project = projects / 'constant-throat-clearing'
    project.mkdir(parents=True)
    (project / 'project.json').write_text(json.dumps({
        'project_id':'legacy-p1',
        'anchor_title':'Constant Throat Clearing? The Real Causes of Phlegm in Your Throat'
    }), encoding='utf-8')
    youtube_aid = register_youtube_only_video(db, title='Constant Throat Clearing? The Real Causes of Phlegm in Your Throat', youtube_video_id='f0ya7l9m9sQ')
    r = auto_link_existing_projects(db, projects)
    assert r['linked'] == 0
    rows = list_videos(db)
    assert len(rows) == 2
    yt = next(v for v in rows if v['analytics_id'] == youtube_aid)
    project_row = next(v for v in rows if v.get('project_id') == 'legacy-p1')
    assert yt['source_type'] == 'youtube_only'
    assert not project_row['youtube_video_id']

from pathlib import Path
import pandas as pd
from analytics_db import (
    init_db, register_youtube_only_video, snapshot_timestamped_transcript,
    import_retention_curve, scene_retention_mapping
)

def test_retention_curve_maps_to_transcript_segments(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    init_db(db)
    aid = register_youtube_only_video(db, title="Retention Test", youtube_video_id="AAAAA111111")
    snapshot_timestamped_transcript(
        db, aid,
        "[00:00:00] Hook\n"
        "[00:00:10] Explanation\n"
        "[00:00:20] Main point\n"
        "[00:00:30] Close"
    )
    retention = pd.DataFrame([
        {"Video time":"0:00","Audience retention (%)":100},
        {"Video time":"0:05","Audience retention (%)":90},
        {"Video time":"0:10","Audience retention (%)":80},
        {"Video time":"0:15","Audience retention (%)":78},
        {"Video time":"0:20","Audience retention (%)":76},
        {"Video time":"0:25","Audience retention (%)":60},
        {"Video time":"0:30","Audience retention (%)":58},
        {"Video time":"0:33","Audience retention (%)":57},
    ])
    result = import_retention_curve(db, aid, retention, source_file="retention.csv")
    assert result["points"] == 8
    mapped = scene_retention_mapping(db, aid)
    assert len(mapped) == 4
    assert list(mapped["scene_id"]) == ["TS0001","TS0002","TS0003","TS0004"]
    # Third segment has the strongest drop in this fixture.
    third = mapped[mapped["scene_id"]=="TS0003"].iloc[0]
    assert third["retention_delta"] < -10

def test_average_percentage_viewed_summary_is_rejected(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    init_db(db)
    aid = register_youtube_only_video(db, title="Summary Test", youtube_video_id="BBBBB222222")
    snapshot_timestamped_transcript(db, aid, "[00:00:00] A\n[00:00:10] B")
    summary = pd.DataFrame([{"Average percentage viewed (%)": 35.0, "Views": 100}])
    try:
        import_retention_curve(db, aid, summary)
    except Exception as exc:
        assert "not a timestamp-by-timestamp" in str(exc)
    else:
        raise AssertionError("Expected summary CSV rejection")

def test_youtube_zero_to_99_positions_do_not_create_false_terminal_spike(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    init_db(db)
    aid = register_youtube_only_video(db, title="Position Scale Test", youtube_video_id="CCCCC333333")
    snapshot_timestamped_transcript(db, aid, "[00:00:00] A\n[00:25:00] B")
    # Mirrors YouTube All.csv position scale: integer 0..99.
    retention = pd.DataFrame({
        "Video position (%)": list(range(100)),
        "Absolute audience retention (%)": [102.65] + [80 - (i * 0.7) for i in range(1, 99)] + [10.62],
    })
    import_retention_curve(db, aid, retention, source_file="All.csv")
    from analytics_db import retention_points_df
    pts = retention_points_df(db, aid)
    assert pts["time_sec"].is_monotonic_increasing
    assert pts.iloc[-1]["position_percent"] == 99
    assert pts.iloc[-1]["retention_percent"] == 10.62
    assert pts.iloc[-1]["time_sec"] < 1500

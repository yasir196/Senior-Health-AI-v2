from pathlib import Path
import pandas as pd
from analytics_db import (
    init_db, bulk_import_channel_content_csv, snapshot_timestamped_transcript,
    import_retention_curve, list_videos, cross_video_script_pattern_learning
)

def test_cross_video_pattern_promotes_after_three_videos(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    init_db(db)

    content_rows = []
    for idx, vid in enumerate(["AAAAA111111","BBBBB222222","CCCCC333333"]):
        content_rows.append({
            "Content": vid,
            "Video title": f"Video {idx+1}",
            "Video publish time": "Aug 5, 2026",
            "Views": 100 + idx,
            "Thumbnail impressions": 1000 + idx,
            "Thumbnail click-through rate (%)": 5.0,
            "Average percentage viewed (%)": 30.0,
            "Average view duration": "5:00",
        })
    bulk_import_channel_content_csv(db, pd.DataFrame(content_rows))

    videos = list_videos(db)
    by_vid = {v["youtube_video_id"]: v["analytics_id"] for v in videos}

    # Same opening structure across 3 videos: "before we go further" triggers delayed-payoff hypothesis.
    transcript = (
        "[00:00:00] Here is the problem you recognize. Before we go further, there is one thing to understand.\n"
        "[00:00:10] First, let us look at the setup before the main answer.\n"
        "[00:00:20] The useful answer comes next.\n"
        "[00:00:30] Now here is the practical point.\n"
        "[00:00:40] Continue with the explanation."
    )
    retention = pd.DataFrame([
        {"Video time":"0:00","Audience retention (%)":100},
        {"Video time":"0:10","Audience retention (%)":90},
        {"Video time":"0:20","Audience retention (%)":80},
        {"Video time":"0:30","Audience retention (%)":68},
        {"Video time":"0:40","Audience retention (%)":65},
        {"Video time":"0:43","Audience retention (%)":64},
    ])

    for vid in by_vid:
        aid = by_vid[vid]
        snapshot_timestamped_transcript(db, aid, transcript)
        import_retention_curve(db, aid, retention, source_file="All.csv")

    data = cross_video_script_pattern_learning(db)
    patterns = data["patterns"]
    row = patterns[patterns["Script Pattern"] == "Delayed payoff / preamble in the opening"].iloc[0]
    assert int(row["Videos"]) == 3
    assert row["Confidence"] == "CHANNEL PATTERN"
    assert data["summary"]["channel_patterns"] >= 1

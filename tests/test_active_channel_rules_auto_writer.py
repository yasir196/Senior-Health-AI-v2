from pathlib import Path
import pandas as pd
from analytics_db import (
    init_db, bulk_import_channel_content_csv, list_videos,
    snapshot_timestamped_transcript, import_retention_curve,
    sync_active_channel_script_rules, active_channel_script_rules,
    render_active_channel_rules_markdown, write_active_channel_rules_file
)

def test_rule_activates_at_three_and_writes_writer_artifact(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    init_db(db)

    ids = ["AAAAA111111","BBBBB222222","CCCCC333333"]
    df = pd.DataFrame([{
        "Content": vid,
        "Video title": f"Video {i}",
        "Video publish time": "Aug 5, 2026",
        "Views": 100,
        "Thumbnail impressions": 1000,
        "Thumbnail click-through rate (%)": 5.0,
        "Average percentage viewed (%)": 30.0,
        "Average view duration": "5:00",
    } for i, vid in enumerate(ids, 1)])
    bulk_import_channel_content_csv(db, df)

    by_vid = {v["youtube_video_id"]: v["analytics_id"] for v in list_videos(db)}

    transcript = "\n".join([
        "[00:00:00] Here is the problem. Before we go further, there is setup first.",
        "[00:00:10] First, let us explain more before the answer.",
        "[00:00:20] The answer comes later.",
        "[00:00:30] Now here is the practical point.",
        "[00:00:40] Continue.",
    ])
    retention = pd.DataFrame([
        {"Video time":"0:00","Audience retention (%)":100},
        {"Video time":"0:10","Audience retention (%)":90},
        {"Video time":"0:20","Audience retention (%)":80},
        {"Video time":"0:30","Audience retention (%)":68},
        {"Video time":"0:40","Audience retention (%)":65},
        {"Video time":"0:43","Audience retention (%)":64},
    ])

    for vid in ids:
        aid = by_vid[vid]
        snapshot_timestamped_transcript(db, aid, transcript)
        import_retention_curve(db, aid, retention, source_file="All.csv")

    result = sync_active_channel_script_rules(db)
    assert result["active"] >= 1

    active = active_channel_script_rules(db)
    assert not active.empty
    assert set(active["status"]) == {"ACTIVE"}

    md = render_active_channel_rules_markdown(db)
    assert "# ACTIVE CHANNEL SCRIPT RULES" in md
    assert "Instruction:" in md

    artifact = tmp_path / "active_channel_script_rules.md"
    write_active_channel_rules_file(db, artifact)
    assert artifact.is_file()
    assert "ACTIVE CHANNEL SCRIPT RULES" in artifact.read_text(encoding="utf-8")

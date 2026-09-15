
from pathlib import Path
import json
import pandas as pd

from analytics_db import (
    archive_production_learning_checkpoint,
    build_production_timeline_snapshot,
    get_video,
    scene_snapshot_df,
)

def _project(tmp_path: Path) -> Path:
    p = tmp_path / "Projects" / "demo"
    p.mkdir(parents=True)
    (p / "project.json").write_text(json.dumps({
        "project_id": "seo-prod-learning-demo",
        "anchor_title": "Demo Video",
        "created_at": "2026-09-09T00:00:00",
    }), encoding="utf-8")
    (p / "06_final_script.md").write_text("Final script", encoding="utf-8")
    pd.DataFrame([
        {"scene_id":"S001","start_time":"0:00","end_time":"0:10","duration_sec":10,
         "visual_mode":"EXPLANATORY","recommended_asset_type":"AI_IMAGE","overlay_instruction":""},
        {"scene_id":"S002","start_time":"0:10","end_time":"0:20","duration_sec":10,
         "visual_mode":"DIRECT","recommended_asset_type":"AVATAR","overlay_instruction":""},
    ]).to_csv(p / "07_production_sheet.csv", index=False)
    pd.DataFrame([
        {"Scene ID":"S001","Actual Audio Start":"0:00","Actual Audio End":"0:12","Duration":12,"Script Text":"One"},
        {"Scene ID":"S002","Actual Audio Start":"0:12","Actual Audio End":"0:27","Duration":15,"Script Text":"Two"},
    ]).to_csv(p / "08_actual_timeline.csv", index=False)
    return p

def test_merge_uses_actual_timeline_timing_and_production_metadata(tmp_path):
    p = _project(tmp_path)
    out = tmp_path / "snapshot.csv"
    df = build_production_timeline_snapshot(
        p / "08_actual_timeline.csv", p / "07_production_sheet.csv", out
    )
    assert list(df["actual_start_sec"]) == [0.0, 12.0]
    assert list(df["actual_end_sec"]) == [12.0, 27.0]
    assert list(df["actual_duration_sec"]) == [12.0, 15.0]
    assert list(df["production_recommended_asset_type"]) == ["AI_IMAGE", "AVATAR"]
    assert list(df["production_visual_mode"]) == ["EXPLANATORY", "DIRECT"]
    # Planned timing is retained only as prefixed audit metadata.
    assert list(df["production_end_time"]) == ["0:10", "0:20"]
    assert set(df["timing_authority"]) == {"08_actual_timeline.csv"}

def test_seo_checkpoint_archives_assets_and_refreshes_scene_db_idempotently(tmp_path):
    p = _project(tmp_path)
    db = tmp_path / "Analytics" / "senior_health_analytics.db"

    first = archive_production_learning_checkpoint(db, p)
    second = archive_production_learning_checkpoint(db, p)
    assert first["analytics_id"] == second["analytics_id"]
    assert first["merged_rows"] == 2
    archive = db.parent / "project_assets" / first["analytics_id"]
    for name in (
        "06_final_script.md",
        "07_production_sheet.csv",
        "08_actual_timeline.csv",
        "production_timeline_snapshot.csv",
    ):
        assert (archive / name).is_file()

    scenes = scene_snapshot_df(db, first["analytics_id"])
    assert len(scenes) == 2
    s1 = scenes[scenes["scene_id"] == "S001"].iloc[0]
    assert float(s1["end_sec"]) == 12.0
    assert s1["asset_type"] == "AI_IMAGE"
    assert s1["visual_mode"] == "EXPLANATORY"

def test_merge_rejects_missing_scene_mapping(tmp_path):
    p = _project(tmp_path)
    prod = pd.read_csv(p / "07_production_sheet.csv").iloc[:1]
    prod.to_csv(p / "07_production_sheet.csv", index=False)
    out = tmp_path / "snapshot.csv"
    import pytest
    from analytics_db import AnalyticsDBError
    with pytest.raises(AnalyticsDBError, match="Scene ID mismatch"):
        build_production_timeline_snapshot(
            p / "08_actual_timeline.csv", p / "07_production_sheet.csv", out
        )
    assert not out.exists()

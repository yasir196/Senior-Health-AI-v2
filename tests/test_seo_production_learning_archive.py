
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
    return p

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
        "production_timeline_snapshot.csv",
    ):
        assert (archive / name).is_file()

    scenes = scene_snapshot_df(db, first["analytics_id"])
    assert len(scenes) == 2
    s1 = scenes[scenes["scene_id"] == "S001"].iloc[0]
    assert float(s1["end_sec"]) == 10.0
    assert s1["asset_type"] == "AI_IMAGE"
    assert s1["visual_mode"] == "EXPLANATORY"


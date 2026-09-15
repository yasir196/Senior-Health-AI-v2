
from pathlib import Path
import sqlite3
import pandas as pd
import analytics_db as adb

def _db(tmp_path):
    db=tmp_path/"Analytics"/"senior_health_analytics.db"
    db.parent.mkdir(parents=True)
    adb.init_db(db)
    aid="aid-1"
    with sqlite3.connect(db) as con:
        con.execute("""INSERT INTO videos(analytics_id,source_type,created_at,updated_at)
                       VALUES(?,?,?,?)""",(aid,"project_linked",adb._now(),adb._now()))
    return db,aid

def _mapped():
    return pd.DataFrame([{
        "scene_id":"S001","source":"actual_timeline","start_sec":0.0,"end_sec":8.0,
        "duration_sec":8.0,"script_text":"x","visual_mode":"AVATAR","asset_type":"PLANNED",
        "overlay_type":"OLD","retention_start":90.0,"retention_end":89.0,
        "retention_avg":89.5,"retention_delta":-1.0,"retention_signal":"STABLE"
    }])

def test_missing_archive_blocks_and_cleans_old_evidence(tmp_path):
    db,aid=_db(tmp_path)
    with sqlite3.connect(db) as con:
        con.execute("""INSERT INTO production_learning_scenes(
        analytics_id,scene_id,start_sec,end_sec,evidence_status,source,updated_at)
        VALUES(?,?,?,?,?,?,?)""",(aid,"S001",0,8,"OBSERVATION","legacy",adb._now()))
    gated=adb._apply_production_provenance_gate(db,aid,_mapped())
    assert gated.loc[0,"production_provenance"]=="UNVERIFIED"
    assert pd.isna(gated.loc[0,"visual_mode"])
    result=adb.sync_production_learning_scenes(db,aid,mapped=gated)
    assert result["blocked_unverified"]==1
    assert adb.production_learning_scene_df(db,aid).empty

def test_verified_snapshot_supplies_metadata(tmp_path):
    db,aid=_db(tmp_path)
    d=db.parent/"project_assets"/aid
    d.mkdir(parents=True)
    pd.DataFrame([{
        "scene_id":"S001","actual_start_sec":0.0,"actual_end_sec":8.0,
        "actual_duration_sec":8.0,"timing_authority":"08_actual_timeline.csv",
        "production_Visual Mode":"AI_IMAGE",
        "production_recommended_asset_type":"AI_IMAGE",
        "production_Overlay Type":"NONE",
    }]).to_csv(d/"production_timeline_snapshot.csv",index=False)
    gated=adb._apply_production_provenance_gate(db,aid,_mapped())
    assert gated.loc[0,"production_provenance"]=="VERIFIED"
    assert gated.loc[0,"visual_mode"]=="AI_IMAGE"
    assert gated.loc[0,"asset_type"]=="AI_IMAGE"
    result=adb.sync_production_learning_scenes(db,aid,mapped=gated)
    assert result["stored"]==1

def test_wrong_analytics_archive_does_not_verify(tmp_path):
    db,aid=_db(tmp_path)
    d=db.parent/"project_assets"/"some-other-id"
    d.mkdir(parents=True)
    pd.DataFrame([{"scene_id":"S001","actual_start_sec":0,"actual_end_sec":8,
                  "timing_authority":"08_actual_timeline.csv","production_Visual Mode":"AVATAR"}]).to_csv(
        d/"production_timeline_snapshot.csv",index=False)
    assert not adb.production_provenance(db,aid)["verified"]

def test_malformed_snapshot_blocked(tmp_path):
    db,aid=_db(tmp_path)
    d=db.parent/"project_assets"/aid
    d.mkdir(parents=True)
    pd.DataFrame([{"scene_id":"S001","production_Visual Mode":"AVATAR"}]).to_csv(
        d/"production_timeline_snapshot.csv",index=False)
    assert not adb.production_provenance(db,aid)["verified"]

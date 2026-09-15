from pathlib import Path
import json
import pandas as pd
from analytics_db import (
    ensure_project_record, snapshot_actual_timeline, import_retention_curve,
    scene_retention_mapping, production_learning_scene_df, production_learning_summary, build_production_timeline_snapshot,
)

def make_project(tmp_path: Path, pid='p1'):
    p=tmp_path/'Projects'/pid; p.mkdir(parents=True)
    (p/'project.json').write_text(json.dumps({'project_id':pid,'anchor_title':pid}),encoding='utf-8')
    pd.DataFrame([
      {'Scene ID':'S001','Actual Audio Start':'0:00','Actual Audio End':'0:10','Duration':10,'Script Text':'hook'},
      {'Scene ID':'S002','Actual Audio Start':'0:10','Actual Audio End':'0:20','Duration':10,'Script Text':'explain'},
    ]).to_csv(p/'08_actual_timeline.csv',index=False)
    pd.DataFrame([
      {'scene_id':'S001','visual_mode':'DIRECT','recommended_asset_type':'AVATAR','overlay_type':''},
      {'scene_id':'S002','visual_mode':'EXPLANATORY','recommended_asset_type':'AI_IMAGE','overlay_type':''},
    ]).to_csv(p/'07_production_sheet.csv',index=False)
    return p

def map_video(db,p):
    aid=ensure_project_record(db,p)
    snapshot_actual_timeline(db,aid,p/'08_actual_timeline.csv',production_sheet_path=p/'07_production_sheet.csv')
    archive=db.parent/'project_assets'/aid
    archive.mkdir(parents=True,exist_ok=True)
    build_production_timeline_snapshot(
        p/'08_actual_timeline.csv', p/'07_production_sheet.csv',
        archive/'production_timeline_snapshot.csv'
    )
    curve=pd.DataFrame({'Video position (%)':[0,50,100],'Absolute audience retention (%)':[100,90,80]})
    import_retention_curve(db,aid,curve,source_file='ret.csv')
    scene_retention_mapping(db,aid)
    return aid

def test_scene_evidence_persists_production_plus_retention(tmp_path):
    db=tmp_path/'Analytics'/'senior_health_analytics.db'; p=make_project(tmp_path)
    aid=map_video(db,p)
    df=production_learning_scene_df(db,aid)
    assert len(df)==2
    assert set(df.asset_type)=={'AVATAR','AI_IMAGE'}
    assert set(df.evidence_status)=={'OBSERVATION'}
    assert df.retention_delta.notna().all()

def test_cross_video_status_is_conservative_and_no_active_rule(tmp_path):
    db=tmp_path/'Analytics'/'senior_health_analytics.db'
    for pid in ('p1','p2'):
        map_video(db,make_project(tmp_path,pid))
    s=production_learning_summary(db)
    assert not s.empty
    assert set(s.pattern_status)=={'REPEATED SIGNAL'}
    assert 'ACTIVE' not in set(s.pattern_status)

def test_transcript_only_metadata_is_not_invented(tmp_path):
    db=tmp_path/'Analytics'/'senior_health_analytics.db'; p=make_project(tmp_path)
    aid=ensure_project_record(db,p)
    snapshot_actual_timeline(db,aid,p/'08_actual_timeline.csv',production_sheet_path=None)
    curve=pd.DataFrame({'Video position (%)':[0,50,100],'Absolute audience retention (%)':[100,90,80]})
    import_retention_curve(db,aid,curve,source_file='ret.csv')
    scene_retention_mapping(db,aid)
    assert production_learning_scene_df(db,aid).empty

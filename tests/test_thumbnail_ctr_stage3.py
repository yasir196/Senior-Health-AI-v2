from pathlib import Path
import tempfile
from analytics_db import (init_db,_db_connect,record_thumbnail_snapshot,record_thumbnail_analysis,
    join_thumbnail_ctr_evidence,thumbnail_ctr_evidence_df,_thumbnail_evidence_weight,AnalyticsDBError)


def seed(db, with_metrics=True):
    init_db(db)
    with _db_connect(db) as con:
        con.execute("INSERT INTO videos(analytics_id,source_type,youtube_video_id,created_at,updated_at) VALUES('a1','project_linked','abcDEF12345','2026-01-01','2026-01-01')")
        if with_metrics:
            con.execute("INSERT INTO performance_snapshots(analytics_id,imported_at,report_kind,impressions,ctr_percent) VALUES('a1','2026-01-03','performance',10000,6.5)")
        con.commit()
    sid=record_thumbnail_snapshot(db,'a1',youtube_video_id='abcDEF12345',downloaded_at='2026-01-02',source_url='x',source_variant='maxresdefault',file_path='/tmp/x.jpg',width=1280,height=720,sha256='sha')
    record_thumbnail_analysis(db,sid,analytics_id='a1',youtube_video_id='abcDEF12345',analyzed_at='2026-01-02',model='m',title_at_analysis='T',features={'hero_subject':'salmon','arrow_present':True},raw_response='{}')
    return sid


def test_stage3_schema_migrates_without_reset():
    db=Path(tempfile.mkdtemp())/'Analytics'/'senior_health_analytics.db'; init_db(db)
    with _db_connect(db) as con:
        cols={r['name'] for r in con.execute('PRAGMA table_info(thumbnail_ctr_evidence)').fetchall()}
        assert {'thumbnail_snapshot_id','thumbnail_analysis_id','ctr_percent','impressions','attribution_status','evidence_weight'} <= cols
        assert int(con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]) >= 6


def test_stage3_joins_features_to_measured_performance_and_keeps_caveat():
    db=Path(tempfile.mkdtemp())/'Analytics'/'senior_health_analytics.db'; seed(db)
    row=join_thumbnail_ctr_evidence(db,'a1')
    assert row['ctr_percent']==6.5 and row['impressions']==10000
    assert row['metric_source']=='performance_snapshot'
    assert row['attribution_status']=='historical_thumbnail_version_uncertain'
    df=thumbnail_ctr_evidence_df(db,'a1')
    assert len(df)==1 and df.iloc[0]['hero_subject']=='salmon' and int(df.iloc[0]['arrow_present'])==1


def test_stage3_prefers_weighted_reach_days():
    db=Path(tempfile.mkdtemp())/'Analytics'/'senior_health_analytics.db'; seed(db)
    with _db_connect(db) as con:
        con.execute("INSERT INTO reach_daily(analytics_id,report_date,impressions,ctr_percent,imported_at) VALUES('a1','2026-01-01',100,10,'2026-01-04')")
        con.execute("INSERT INTO reach_daily(analytics_id,report_date,impressions,ctr_percent,imported_at) VALUES('a1','2026-01-02',900,5,'2026-01-04')")
        con.commit()
    row=join_thumbnail_ctr_evidence(db,'a1')
    assert row['metric_source']=='reach_daily_weighted'
    assert row['impressions']==1000 and abs(row['ctr_percent']-5.5)<1e-9


def test_stage3_requires_measured_ctr_and_impressions():
    db=Path(tempfile.mkdtemp())/'Analytics'/'senior_health_analytics.db'; seed(db,False)
    try: join_thumbnail_ctr_evidence(db,'a1')
    except AnalyticsDBError as exc: assert 'No measured CTR + impressions' in str(exc)
    else: raise AssertionError('expected failure')


def test_stage3_sample_weight_increases_with_impressions():
    assert _thumbnail_evidence_weight(100) < _thumbnail_evidence_weight(10000) < _thumbnail_evidence_weight(100000)

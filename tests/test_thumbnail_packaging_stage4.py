from pathlib import Path
import tempfile
from analytics_db import (
    init_db,_db_connect,record_thumbnail_snapshot,record_thumbnail_analysis,
    join_thumbnail_ctr_evidence,build_thumbnail_packaging_comparisons,
    thumbnail_packaging_associations_df,_latest_thumbnail_packaging_evidence,
    AnalyticsDBError,
)


def _seed_video(db, aid, vid, ctr, imp, hero='food', arrow=True, question=True, analysis_suffix=''):
    init_db(db)
    with _db_connect(db) as con:
        con.execute("INSERT INTO videos(analytics_id,source_type,youtube_video_id,created_at,updated_at) VALUES(?,?,?,?,?)",
                    (aid,'project_linked',vid,'2026-01-01','2026-01-01'))
        con.execute("INSERT INTO performance_snapshots(analytics_id,imported_at,report_kind,impressions,ctr_percent) VALUES(?,?,?,?,?)",
                    (aid,'2026-01-03','performance',imp,ctr))
        con.commit()
    sid=record_thumbnail_snapshot(db,aid,youtube_video_id=vid,downloaded_at='2026-01-02',source_url='x',source_variant='maxresdefault',file_path=f'/tmp/{aid}.jpg',width=1280,height=720,sha256='sha'+aid)
    record_thumbnail_analysis(db,sid,analytics_id=aid,youtube_video_id=vid,analyzed_at='2026-01-02',model='m'+analysis_suffix,title_at_analysis='T',features={
        'hero_category':hero,'hero_subject':'salmon' if hero=='food' else 'chair exercise',
        'arrow_present':arrow,'question_hook':question,'presenter_present':True,
        'background_brightness':'dark','visual_complexity':'low','composition_layout':'split',
        'subject_separation':'strong','text_line_count':2,'text_word_count':3,
    },raw_response='{}')
    return join_thumbnail_ctr_evidence(db,aid)


def test_stage4_schema_migrates_without_reset():
    db=Path(tempfile.mkdtemp())/'Analytics'/'senior_health_analytics.db'; init_db(db)
    with _db_connect(db) as con:
        tables={r['name'] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert 'thumbnail_packaging_comparison_runs' in tables
        assert 'thumbnail_packaging_associations' in tables
        assert int(con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]) >= 7


def test_stage4_builds_impression_weighted_associations_without_rule_promotion():
    db=Path(tempfile.mkdtemp())/'Analytics'/'senior_health_analytics.db'
    _seed_video(db,'a1','vid00000001',8.0,100000,arrow=True)
    _seed_video(db,'a2','vid00000002',5.0,10000,arrow=False)
    _seed_video(db,'a3','vid00000003',7.0,50000,arrow=True)
    result=build_thumbnail_packaging_comparisons(db)
    assert result['evidence_videos']==3 and result['associations']>0
    df=thumbnail_packaging_associations_df(db,result['run_id'])
    arrow_yes=df[(df.feature_name=='arrow_present') & (df.feature_value=='1') & (df.context_type=='channel')]
    assert len(arrow_yes)==1
    row=arrow_yes.iloc[0]
    assert int(row.video_count)==2 and row.maturity=='REPEATED SIGNAL'
    assert row.association_direction=='stronger_ctr_association'
    assert 'not a causal rule' in row.interpretation


def test_stage4_contextualizes_by_hero_category():
    db=Path(tempfile.mkdtemp())/'Analytics'/'senior_health_analytics.db'
    _seed_video(db,'a1','vid00000001',8,10000,hero='food',arrow=True)
    _seed_video(db,'a2','vid00000002',5,10000,hero='food',arrow=False)
    _seed_video(db,'a3','vid00000003',6,10000,hero='exercise',arrow=True)
    _seed_video(db,'a4','vid00000004',7,10000,hero='exercise',arrow=False)
    r=build_thumbnail_packaging_comparisons(db)
    df=thumbnail_packaging_associations_df(db,r['run_id'])
    contexts=set(zip(df.context_type,df.context_value))
    assert ('hero_category','food') in contexts and ('hero_category','exercise') in contexts


def test_stage4_latest_evidence_only_prevents_duplicate_video_weighting():
    db=Path(tempfile.mkdtemp())/'Analytics'/'senior_health_analytics.db'
    first=_seed_video(db,'a1','vid00000001',6,10000,arrow=True)
    # Simulate a later Stage-2 re-analysis and Stage-3 join for same immutable thumbnail/video.
    with _db_connect(db) as con:
        sid=con.execute("SELECT id FROM thumbnail_snapshots WHERE analytics_id='a1'").fetchone()['id']
    record_thumbnail_analysis(db,sid,analytics_id='a1',youtube_video_id='vid00000001',analyzed_at='2026-01-04',model='m2',title_at_analysis='T',features={'hero_category':'food','arrow_present':False},raw_response='{}')
    join_thumbnail_ctr_evidence(db,'a1')
    rows=_latest_thumbnail_packaging_evidence(db)
    assert len(rows)==1 and rows[0]['analytics_id']=='a1'


def test_stage4_requires_two_different_videos():
    db=Path(tempfile.mkdtemp())/'Analytics'/'senior_health_analytics.db'
    _seed_video(db,'a1','vid00000001',6,10000)
    try:
        build_thumbnail_packaging_comparisons(db)
    except AnalyticsDBError as exc:
        assert 'at least 2 different videos' in str(exc)
    else:
        raise AssertionError('expected Stage 4 minimum-evidence failure')

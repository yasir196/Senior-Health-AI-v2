from pathlib import Path
import tempfile
from analytics_db import (
    init_db,_db_connect,record_thumbnail_snapshot,record_thumbnail_analysis,
    join_thumbnail_ctr_evidence,build_thumbnail_packaging_comparisons,
    sync_packaging_rule_candidates,all_channel_packaging_rules,
    active_channel_packaging_rules,set_packaging_rule_status,
    write_active_packaging_rules_file,AnalyticsDBError,
)

def seed(db, i, arrow, ctr, imp=10000):
    aid=f'a{i}'; vid=f'vid{i:08d}'
    init_db(db)
    with _db_connect(db) as con:
        con.execute("INSERT INTO videos(analytics_id,source_type,youtube_video_id,created_at,updated_at) VALUES(?,?,?,?,?)",(aid,'project_linked',vid,'2026-01-01','2026-01-01'))
        con.execute("INSERT INTO performance_snapshots(analytics_id,imported_at,report_kind,impressions,ctr_percent) VALUES(?,?,?,?,?)",(aid,'2026-01-03','performance',imp,ctr)); con.commit()
    sid=record_thumbnail_snapshot(db,aid,youtube_video_id=vid,downloaded_at='2026-01-02',source_url='x',source_variant='maxresdefault',file_path=f'/tmp/{aid}.jpg',width=1280,height=720,sha256='sha'+aid)
    record_thumbnail_analysis(db,sid,analytics_id=aid,youtube_video_id=vid,analyzed_at='2026-01-02',model='m',title_at_analysis='T',features={'hero_category':'food','arrow_present':arrow,'presenter_present':True},raw_response='{}')
    join_thumbnail_ctr_evidence(db,aid)

def make_db():
    db=Path(tempfile.mkdtemp())/'Analytics'/'senior_health_analytics.db'
    # 3 arrow=yes and 2 arrow=no -> yes reaches candidate maturity.
    seed(db,1,True,8); seed(db,2,True,7.5); seed(db,3,True,8.5); seed(db,4,False,5); seed(db,5,False,5.5)
    build_thumbnail_packaging_comparisons(db)
    return db

def test_stage5_schema_migrates_without_reset():
    db=Path(tempfile.mkdtemp())/'a.db'; init_db(db)
    with _db_connect(db) as con:
        assert con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='channel_packaging_rules'").fetchone()
        assert int(con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]) >= 8

def test_stage5_creates_candidate_but_never_auto_activates():
    db=make_db(); r=sync_packaging_rule_candidates(db); df=all_channel_packaging_rules(db)
    assert r['eligible_associations'] >= 1
    assert not df.empty and 'CANDIDATE' in set(df.status)
    assert active_channel_packaging_rules(db).empty

def test_stage5_uncertain_candidate_cannot_be_promoted_and_audit_history_is_preserved():
    import pytest
    db=make_db(); sync_packaging_rule_candidates(db); df=all_channel_packaging_rules(db)
    row=df[df.status=='CANDIDATE'].iloc[0]; key=row.rule_key
    with pytest.raises(AnalyticsDBError, match='Cannot promote to ACTIVE'):
        set_packaging_rule_status(db,key,'ACTIVE','reviewed by user')
    assert active_channel_packaging_rules(db).empty
    sync_packaging_rule_candidates(db); assert all_channel_packaging_rules(db).query("rule_key == @key").iloc[0].status=='CANDIDATE'
    set_packaging_rule_status(db,key,'RETIRED','later retired')
    rr=all_channel_packaging_rules(db).query("rule_key == @key").iloc[0]
    assert rr.status=='RETIRED' and rr.review_note=='later retired'

def test_stage5_uncertain_candidate_is_not_written_to_active_artifact():
    import pytest
    db=make_db(); sync_packaging_rule_candidates(db); out=Path(tempfile.mkdtemp())/'active_channel_packaging_rules.md'
    row=all_channel_packaging_rules(db).query("status == 'CANDIDATE'").iloc[0]
    with pytest.raises(AnalyticsDBError, match='Cannot promote to ACTIVE'):
        set_packaging_rule_status(db,row.rule_key,'ACTIVE')
    write_active_packaging_rules_file(db,out)
    assert 'No ACTIVE channel packaging rules yet' in out.read_text()

def test_stage5_needs_stage4_first():
    db=Path(tempfile.mkdtemp())/'a.db'; init_db(db)
    try: sync_packaging_rule_candidates(db)
    except AnalyticsDBError as e: assert 'Stage 4' in str(e)
    else: raise AssertionError('expected Stage 4 prerequisite')

def _seed_clean(db, i, arrow, ctr, imp=10000):
    aid=f'clean{i}'; vid=f'cln{i:08d}'
    init_db(db)
    with _db_connect(db) as con:
        con.execute("INSERT INTO videos(analytics_id,source_type,youtube_video_id,created_at,updated_at) VALUES(?,?,?,?,?)",(aid,'project_linked',vid,'2026-01-01','2026-01-01'))
        con.execute("INSERT INTO reach_daily(analytics_id,report_date,impressions,ctr_percent,imported_at) VALUES(?,?,?,?,?)",(aid,'2026-01-03',imp,ctr,'2026-01-04'))
        con.commit()
    sid=record_thumbnail_snapshot(db,aid,youtube_video_id=vid,downloaded_at='2026-01-02',source_url='x',source_variant='maxresdefault',file_path=f'/tmp/{aid}.jpg',width=1280,height=720,sha256='sha'+aid)
    record_thumbnail_analysis(db,sid,analytics_id=aid,youtube_video_id=vid,analyzed_at='2026-01-02',model='m',title_at_analysis='T',features={'hero_category':'food','arrow_present':arrow,'presenter_present':True},raw_response='{}')
    join_thumbnail_ctr_evidence(db,aid)


def test_stage5_reciprocal_binary_association_becomes_one_review_candidate():
    db=Path(tempfile.mkdtemp())/'a.db'
    for i in range(1,4): _seed_clean(db,i,True,8.0,10000)
    for i in range(4,7): _seed_clean(db,i,False,4.0,10000)
    build_thumbnail_packaging_comparisons(db); sync_packaging_rule_candidates(db)
    df=all_channel_packaging_rules(db)
    arrows=df[(df.context_type=='channel') & (df.feature_name=='arrow_present')]
    assert len(arrows)==1
    assert arrows.iloc[0].direction=='stronger_ctr_association'


def test_stage5_promotion_audit_requires_two_sided_impression_support_and_nonzero_interval():
    from analytics_db import packaging_rule_promotion_audit
    db=Path(tempfile.mkdtemp())/'a.db'
    for i in range(1,4): _seed_clean(db,i,True,8.0,10000)
    for i in range(4,7): _seed_clean(db,i,False,4.0,10000)
    build_thumbnail_packaging_comparisons(db); sync_packaging_rule_candidates(db)
    row=all_channel_packaging_rules(db).query("context_type == 'channel' and feature_name == 'arrow_present'").iloc[0]
    audit=packaging_rule_promotion_audit(db,row.rule_key)
    assert audit['promotion_ready'] is True
    assert audit['feature_videos']==3 and audit['comparison_videos']==3
    assert audit['feature_impressions']==30000 and audit['comparison_impressions']==30000
    assert audit['delta_ci95_low'] > 0
    set_packaging_rule_status(db,row.rule_key,'ACTIVE','fair-comparison reviewed')
    assert len(active_channel_packaging_rules(db))==1


def test_stage5_promotion_audit_blocks_tiny_comparison_impression_cohort():
    from analytics_db import packaging_rule_promotion_audit
    db=Path(tempfile.mkdtemp())/'a.db'
    for i in range(1,4): _seed_clean(db,i,True,8.0,10000)
    for i in range(4,7): _seed_clean(db,i,False,4.0,100)
    build_thumbnail_packaging_comparisons(db); sync_packaging_rule_candidates(db)
    row=all_channel_packaging_rules(db).query("context_type == 'channel' and feature_name == 'arrow_present'").iloc[0]
    audit=packaging_rule_promotion_audit(db,row.rule_key)
    assert audit['promotion_ready'] is False
    assert any('1,000 impressions' in x for x in audit['reasons'])

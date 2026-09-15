from pathlib import Path
import tempfile

from analytics_db import (
    init_db, _db_connect, record_thumbnail_snapshot, record_thumbnail_analysis,
    join_thumbnail_ctr_evidence, build_thumbnail_packaging_comparisons,
    sync_packaging_rule_candidates, all_channel_packaging_rules,
    active_channel_packaging_rules, promote_packaging_signal_cluster,
    write_active_packaging_rules_file,
)


def _seed(db, i, long_text, ctr, imp=10000):
    aid=f'cluster{i}'; vid=f'ct{i:09d}'
    init_db(db)
    with _db_connect(db) as con:
        con.execute("INSERT INTO videos(analytics_id,source_type,youtube_video_id,created_at,updated_at) VALUES(?,?,?,?,?)",
                    (aid,'project_linked',vid,'2026-01-01','2026-01-01'))
        con.execute("INSERT INTO reach_daily(analytics_id,report_date,impressions,ctr_percent,imported_at) VALUES(?,?,?,?,?)",
                    (aid,'2026-01-03',imp,ctr,'2026-01-04'))
        con.commit()
    sid=record_thumbnail_snapshot(db,aid,youtube_video_id=vid,downloaded_at='2026-01-02',source_url='x',source_variant='maxresdefault',file_path=f'/tmp/{aid}.jpg',width=1280,height=720,sha256='sha'+aid)
    features={
        'hero_category':'food', 'presenter_present':True,
        'thumbnail_text':'THIS IS A LONGER SENIOR CLEAR THUMBNAIL MESSAGE' if long_text else 'SHORT TEXT',
        'text_word_count':8 if long_text else 2,
        'text_line_count':4 if long_text else 1,
    }
    record_thumbnail_analysis(db,sid,analytics_id=aid,youtube_video_id=vid,analyzed_at='2026-01-02',model='m',title_at_analysis='T',features=features,raw_response='{}')
    join_thumbnail_ctr_evidence(db,aid)


def test_cluster_promotion_creates_one_active_synthetic_rule_and_artifact():
    db=Path(tempfile.mkdtemp())/'a.db'
    for i in range(1,4): _seed(db,i,True,8.0)
    for i in range(4,7): _seed(db,i,False,4.0)
    build_thumbnail_packaging_comparisons(db)
    sync_packaging_rule_candidates(db)
    df=all_channel_packaging_rules(db)
    reps=df[(df.status=='CANDIDATE') & (df.context_type=='channel') & (df.feature_name=='text_word_count')]
    assert not reps.empty
    rep=reps.iloc[0]
    supports=df[(df.status=='CANDIDATE') & (df.context_type=='channel') & (df.feature_name=='text_line_count')]
    support_keys=supports.rule_key.tolist()
    result=promote_packaging_signal_cluster(db,'Text amount & hierarchy',rep.rule_key,support_keys,'cluster reviewed')
    assert result['status']=='ACTIVE'
    active=active_channel_packaging_rules(db)
    cluster=active[active.feature_name=='signal_cluster']
    assert len(cluster)==1
    assert cluster.iloc[0].feature_value=='Text amount & hierarchy'
    assert 'one correlated pattern' in cluster.iloc[0].guidance_text.lower()
    out=Path(tempfile.mkdtemp())/'active.md'
    write_active_packaging_rules_file(db,out)
    text=out.read_text(encoding='utf-8')
    assert 'Cluster — Text amount & hierarchy' in text
    assert 'CTR deltas' not in text or 'not' in text


def test_cluster_promotion_is_context_specific():
    db=Path(tempfile.mkdtemp())/'a.db'
    for i in range(1,4): _seed(db,i,True,8.0)
    for i in range(4,7): _seed(db,i,False,4.0)
    build_thumbnail_packaging_comparisons(db)
    sync_packaging_rule_candidates(db)
    df=all_channel_packaging_rules(db)
    rep=df[(df.status=='CANDIDATE') & (df.context_type=='channel') & (df.feature_name=='text_word_count')].iloc[0]
    # A support from another context must be ignored by the cluster function.
    other=df[(df.status=='CANDIDATE') & (df.context_type!='channel')]
    other_keys=other.rule_key.tolist()[:2]
    promote_packaging_signal_cluster(db,'Text amount & hierarchy',rep.rule_key,other_keys)
    active=active_channel_packaging_rules(db)
    row=active[active.feature_name=='signal_cluster'].iloc[0]
    assert row.context_type=='channel'

from pathlib import Path
import tempfile
from analytics_db import (init_db,_db_connect,record_thumbnail_snapshot,record_thumbnail_analysis,
                          build_thumbnail_packaging_comparisons,thumbnail_packaging_associations_df)


def _seed(db, idx, words, lines, ctr):
    aid=f'a{idx}'; vid=f'vid{idx:08d}'
    with _db_connect(db) as con:
        con.execute("INSERT INTO videos(analytics_id,project_slug,source_type,youtube_video_id,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                    (aid,aid,'project_linked',vid,'2026-01-01','2026-01-01'))
        con.commit()
    sid=record_thumbnail_snapshot(db,analytics_id=aid,youtube_video_id=vid,downloaded_at='2026-01-02T12:00:00',source_url='x',source_variant='x',file_path=f'/tmp/{aid}.jpg',width=1280,height=720,sha256='x')
    anid=record_thumbnail_analysis(db,sid,analytics_id=aid,youtube_video_id=vid,analyzed_at='2026-01-02',model='m',title_at_analysis='T',features={'hero_category':'food','thumbnail_text':'x','text_word_count':words,'text_line_count':lines},raw_response='{}')
    with _db_connect(db) as con:
        con.execute("INSERT INTO thumbnail_ctr_evidence(thumbnail_snapshot_id,thumbnail_analysis_id,analytics_id,youtube_video_id,joined_at,ctr_percent,impressions,metric_source,attribution_status,evidence_weight) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (sid,anid,aid,vid,'2026-01-03',ctr,2000,'reach_daily_post_snapshot','post_snapshot_window_observed',1.0))
        con.commit()


def test_text_length_and_density_buckets_are_learned_without_reanalysis():
    db=Path(tempfile.mkdtemp())/'a.sqlite'; init_db(db)
    _seed(db,1,9,3,8.0); _seed(db,2,10,3,7.5); _seed(db,3,3,2,4.0); _seed(db,4,2,1,4.5)
    build_thumbnail_packaging_comparisons(db)
    df=thumbnail_packaging_associations_df(db)
    assert ((df.feature_name=='text_length_bucket') & (df.feature_value=='8-10 words')).any()
    assert ((df.feature_name=='text_length_bucket') & (df.feature_value=='1-3 words')).any()
    assert ((df.feature_name=='text_density_bucket') & (df.feature_value=='>2-4 words/line')).any()

def test_thumbnail_agent_consumes_active_text_copy_rules():
    src=(Path(__file__).resolve().parents[1]/'Agents'/'Thumbnail_Agent.md').read_text(encoding='utf-8')
    assert 'Channel Thumbnail-Text Evidence Lock' in src
    assert 'text_length_bucket' in src
    assert 'text_density_bucket' in src
    assert 'If no ACTIVE text-copy rule exists' in src

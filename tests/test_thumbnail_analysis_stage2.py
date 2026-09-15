from pathlib import Path
import tempfile
import json
from analytics_db import init_db, _db_connect, record_thumbnail_snapshot, record_thumbnail_analysis, thumbnail_analysis_df
from thumbnail_analysis import _extract_json


def _seed(db):
    init_db(db)
    with _db_connect(db) as con:
        con.execute("INSERT INTO videos(analytics_id,source_type,youtube_video_id,created_at,updated_at) VALUES('a1','project_linked','abcDEF12345','2026-01-01','2026-01-01')")
        con.commit()
    sid=record_thumbnail_snapshot(db,'a1',youtube_video_id='abcDEF12345',downloaded_at='2026-01-01',source_url='https://example.invalid/x.jpg',source_variant='maxresdefault',file_path='/tmp/x.jpg',width=1280,height=720,sha256='x')
    return sid


def test_json_feature_parser_is_schema_bounded():
    got=_extract_json(json.dumps({'hero_subject':'salmon','arrow_present':True,'extra':'drop'}))
    assert got['hero_subject']=='salmon' and got['arrow_present'] is True and 'extra' not in got


def test_analysis_persists_and_marks_snapshot_analyzed():
    db=Path(tempfile.mkdtemp())/'Analytics'/'senior_health_analytics.db'; sid=_seed(db)
    features=_extract_json(json.dumps({'presenter_present':True,'hero_subject':'salmon','thumbnail_text':'WHY THIS FISH?','confidence':0.91}))
    record_thumbnail_analysis(db,sid,analytics_id='a1',youtube_video_id='abcDEF12345',analyzed_at='2026-01-02',model='test-model',title_at_analysis='Title',features=features,raw_response='{}')
    df=thumbnail_analysis_df(db,'a1')
    assert len(df)==1 and df.iloc[0]['hero_subject']=='salmon' and int(df.iloc[0]['presenter_present'])==1
    with _db_connect(db) as con:
        assert con.execute('SELECT analysis_status FROM thumbnail_snapshots WHERE id=?',(sid,)).fetchone()[0]=='analyzed'


def test_stage2_parser_uses_null_for_missing_visual_boolean_and_derives_text_counts():
    got = _extract_json(json.dumps({
        'thumbnail_text': 'WHY THIS\nFISH?',
        'presenter_present': 'maybe',
        'title_thumbnail_relationship': 'complements',
    }))
    assert got['presenter_present'] is None
    assert got['text_word_count'] == 3
    assert got['text_line_count'] == 2
    assert got['question_hook'] is True
    assert got['title_thumbnail_relationship'] == 'complementary'


def test_stage2_schema_migration_adds_queryable_visual_fields_without_resetting_rows():
    db=Path(tempfile.mkdtemp())/'Analytics'/'senior_health_analytics.db'
    init_db(db)
    with _db_connect(db) as con:
        cols={row['name'] for row in con.execute('PRAGMA table_info(thumbnail_analyses)').fetchall()}
        assert {'hero_category','background_brightness','major_visual_object_count','composition_layout','subject_separation'} <= cols
        version=con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
        assert int(version) >= 5


def test_analysis_persists_new_stage2_fields():
    db=Path(tempfile.mkdtemp())/'Analytics'/'senior_health_analytics.db'; sid=_seed(db)
    features=_extract_json(json.dumps({
        'hero_subject':'salmon fillet','hero_category':'food','background_brightness':'dark',
        'major_visual_object_count':3,'composition_layout':'hero left, presenter right',
        'subject_separation':'high'
    }))
    record_thumbnail_analysis(db,sid,analytics_id='a1',youtube_video_id='abcDEF12345',analyzed_at='2026-01-02',model='test-model',title_at_analysis='Title',features=features,raw_response='{}')
    row=thumbnail_analysis_df(db,'a1').iloc[0]
    assert row['hero_category']=='food'
    assert row['background_brightness']=='dark'
    assert int(row['major_visual_object_count'])==3
    assert row['subject_separation']=='high'

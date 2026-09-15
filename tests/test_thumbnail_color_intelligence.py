from pathlib import Path
from analytics_db import init_db, _db_connect, record_thumbnail_snapshot, record_thumbnail_analysis, build_thumbnail_packaging_comparisons


def _add(db, aid, vid, ctr, imp, bg, scheme, accent):
    with _db_connect(db) as con:
        con.execute("INSERT INTO videos(analytics_id,source_type,youtube_video_id,created_at,updated_at) VALUES(?,?,?,?,?)",(aid,"project_linked",vid,"2026-01-01","2026-01-01")); con.commit()
    sid=record_thumbnail_snapshot(db, analytics_id=aid, youtube_video_id=vid, downloaded_at='2026-01-01T00:00:00', source_url='x', source_variant='maxresdefault', file_path='/tmp/x.jpg', sha256=aid, width=1280, height=720)
    an=record_thumbnail_analysis(db,sid,analytics_id=aid,youtube_video_id=vid,analyzed_at='2026-01-02',model='m',title_at_analysis='T',features={'background_color_family':bg,'dominant_palette':('dark navy | white | yellow' if bg=='dark navy' else 'light cream | red | white'),'text_color_scheme':scheme,'accent_color_family':accent,'palette_temperature':('cool' if bg=='dark navy' else 'warm'),'contrast_level':('high' if bg=='dark navy' else 'medium')},raw_response='{}')
    with _db_connect(db) as con:
        con.execute("INSERT INTO thumbnail_ctr_evidence(thumbnail_snapshot_id,thumbnail_analysis_id,analytics_id,youtube_video_id,joined_at,ctr_percent,impressions,metric_source,attribution_status,evidence_weight) VALUES(?,?,?,?,?,?,?,?,?,?)",(sid,an,aid,vid,'2026-01-03',ctr,imp,'reach_daily_post_snapshot','post_snapshot_window_observed',1.0)); con.commit()


def test_color_features_flow_into_packaging_learning(tmp_path: Path):
    db=tmp_path/'a.db'; init_db(db)
    for n in range(3): _add(db,f'a{n}',f'vid0000000{n}',7+n/10,2000,'dark navy','white + yellow','red')
    for n in range(3,6): _add(db,f'a{n}',f'vid0000000{n}',5+n/10,2000,'light cream','red + white','yellow')
    build_thumbnail_packaging_comparisons(db)
    with _db_connect(db) as con:
        names={r[0] for r in con.execute('SELECT DISTINCT feature_name FROM thumbnail_packaging_associations')}
    assert {'background_color_family','dominant_palette','text_color_scheme','accent_color_family','palette_temperature','contrast_level'} <= names

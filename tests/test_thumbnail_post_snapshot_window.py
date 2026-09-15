from pathlib import Path
import tempfile

from analytics_db import (
    init_db, _db_connect, record_thumbnail_snapshot, record_thumbnail_analysis,
    join_thumbnail_ctr_evidence, build_thumbnail_packaging_comparisons,
    sync_packaging_rule_candidates, all_channel_packaging_rules,
    set_packaging_rule_status, AnalyticsDBError,
)


def _seed_video(db, aid, vid, snapshot_date='2026-01-02', feature_value='complementary'):
    init_db(db)
    with _db_connect(db) as con:
        con.execute(
            "INSERT INTO videos(analytics_id,source_type,youtube_video_id,created_at,updated_at) VALUES(?,?,?,?,?)",
            (aid, 'project_linked', vid, '2026-01-01', '2026-01-01'),
        )
        con.commit()
    sid = record_thumbnail_snapshot(
        db, aid, youtube_video_id=vid, downloaded_at=f'{snapshot_date}T12:00:00',
        source_url='x', source_variant='maxresdefault', file_path=f'/tmp/{aid}.jpg',
        width=1280, height=720, sha256=f'sha-{aid}',
    )
    record_thumbnail_analysis(
        db, sid, analytics_id=aid, youtube_video_id=vid, analyzed_at=f'{snapshot_date}T12:01:00',
        model='m', title_at_analysis='T',
        features={'hero_category':'food','title_thumbnail_relationship':feature_value}, raw_response='{}',
    )
    return sid


def test_stage3_uses_only_days_after_snapshot_when_available():
    db = Path(tempfile.mkdtemp())/'Analytics'/'senior_health_analytics.db'
    _seed_video(db, 'a1', 'abcDEF12345')
    with _db_connect(db) as con:
        # These two rows must be excluded from the clean future window.
        con.execute("INSERT INTO reach_daily(analytics_id,report_date,impressions,ctr_percent,imported_at) VALUES('a1','2026-01-01',1000,10,'2026-01-05')")
        con.execute("INSERT INTO reach_daily(analytics_id,report_date,impressions,ctr_percent,imported_at) VALUES('a1','2026-01-02',1000,8,'2026-01-05')")
        # Only these rows count: weighted CTR = (100*4 + 900*6)/1000 = 5.8
        con.execute("INSERT INTO reach_daily(analytics_id,report_date,impressions,ctr_percent,imported_at) VALUES('a1','2026-01-03',100,4,'2026-01-05')")
        con.execute("INSERT INTO reach_daily(analytics_id,report_date,impressions,ctr_percent,imported_at) VALUES('a1','2026-01-04',900,6,'2026-01-05')")
        con.commit()
    row = join_thumbnail_ctr_evidence(db, 'a1')
    assert row['metric_source'] == 'reach_daily_post_snapshot'
    assert row['attribution_status'] == 'post_snapshot_window_observed'
    assert row['metric_start_date'] == '2026-01-03'
    assert row['metric_end_date'] == '2026-01-04'
    assert row['metric_days'] == 2
    assert row['impressions'] == 1000
    assert abs(row['ctr_percent'] - 5.8) < 1e-9


def test_stage3_same_day_only_does_not_claim_clean_window():
    db = Path(tempfile.mkdtemp())/'Analytics'/'senior_health_analytics.db'
    _seed_video(db, 'a1', 'abcDEF12345')
    with _db_connect(db) as con:
        con.execute("INSERT INTO reach_daily(analytics_id,report_date,impressions,ctr_percent,imported_at) VALUES('a1','2026-01-02',1000,8,'2026-01-05')")
        con.commit()
    row = join_thumbnail_ctr_evidence(db, 'a1')
    assert row['metric_source'] == 'reach_daily_weighted'
    assert row['attribution_status'] == 'historical_thumbnail_version_uncertain'


def test_stage4_requires_clean_attribution_on_both_sides():
    db = Path(tempfile.mkdtemp())/'Analytics'/'senior_health_analytics.db'
    # 3 complementary clean videos
    for i in range(3):
        aid=f'c{i}'; _seed_video(db, aid, f'vidC{i}ABCDE', feature_value='complementary')
        with _db_connect(db) as con:
            con.execute("INSERT INTO reach_daily(analytics_id,report_date,impressions,ctr_percent,imported_at) VALUES(?,?,?,?,?)",
                        (aid,'2026-01-03',1000,6.0,'2026-01-05')); con.commit()
        join_thumbnail_ctr_evidence(db, aid)
    # 3 duplicate HISTORICAL-only videos (same-day rows, no clean post rows)
    for i in range(3):
        aid=f'd{i}'; _seed_video(db, aid, f'vidD{i}ABCDE', feature_value='duplicate')
        with _db_connect(db) as con:
            con.execute("INSERT INTO reach_daily(analytics_id,report_date,impressions,ctr_percent,imported_at) VALUES(?,?,?,?,?)",
                        (aid,'2026-01-02',1000,3.0,'2026-01-05')); con.commit()
        join_thumbnail_ctr_evidence(db, aid)
    result=build_thumbnail_packaging_comparisons(db)
    assert result['associations'] > 0
    with _db_connect(db) as con:
        row=con.execute("SELECT attribution_status FROM thumbnail_packaging_associations WHERE feature_name='title_thumbnail_relationship' AND feature_value='complementary' ORDER BY id DESC LIMIT 1").fetchone()
    assert row['attribution_status'] == 'mixed_attribution_caveats'


def test_stage5_can_promote_only_all_clean_post_snapshot_comparison():
    db = Path(tempfile.mkdtemp())/'Analytics'/'senior_health_analytics.db'
    # Build two clean cohorts, 3 videos each.
    for prefix, feature, ctr in [('c','complementary',6.0),('d','duplicate',3.0)]:
        for i in range(3):
            aid=f'{prefix}{i}'; _seed_video(db, aid, f'{prefix.upper()}vid{i}ABCDE', feature_value=feature)
            with _db_connect(db) as con:
                con.execute("INSERT INTO reach_daily(analytics_id,report_date,impressions,ctr_percent,imported_at) VALUES(?,?,?,?,?)",
                            (aid,'2026-01-03',1000,ctr,'2026-01-05')); con.commit()
            join_thumbnail_ctr_evidence(db, aid)
    build_thumbnail_packaging_comparisons(db)
    sync_packaging_rule_candidates(db)
    rules=all_channel_packaging_rules(db)
    row=rules[(rules.feature_name=='title_thumbnail_relationship') & (rules.feature_value=='complementary')].iloc[0]
    assert row.attribution_status == 'post_snapshot_window_observed'
    out=set_packaging_rule_status(db, row.rule_key, 'ACTIVE', 'clean future-window test')
    assert out['status']=='ACTIVE'

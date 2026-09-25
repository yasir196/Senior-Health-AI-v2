from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from Thumbnail_Pipeline.adapters.performance import read_performance_export
from Thumbnail_Pipeline.adapters.v2_assets import V2AssetsAdapter
from Thumbnail_Pipeline.intelligence.join import join_by_asset_id
from Thumbnail_Pipeline.adapters.v2_analytics_db import V2AnalyticsReadOnlyAdapter
import sqlite3


def test_discovers_existing_v2_thumbnail_without_mutation(tmp_path):
    thumb = tmp_path / "Analytics" / "youtube_assets" / "abc" / "thumbnails" / "x.jpg"
    thumb.parent.mkdir(parents=True)
    thumb.write_bytes(b"unchanged")
    before = thumb.read_bytes()
    rows = V2AssetsAdapter(tmp_path).thumbnails()
    assert [(r.asset_id, r.path.name) for r in rows] == [("abc", "x.jpg")]
    assert thumb.read_bytes() == before


def test_performance_aliases_and_join(tmp_path):
    csv_path = tmp_path / "performance.csv"
    csv_path.write_text(
        "project_id,youtube_video_id,impressions_click_through_rate,impressions,views\n"
        "abc,vid1,6.5,10000,650\n",
        encoding="utf-8",
    )
    perf = read_performance_export(csv_path)
    assert perf[0]["asset_id"] == "abc"
    assert perf[0]["video_id"] == "vid1"
    joined = join_by_asset_id([{"asset_id": "abc", "features": {}}], perf)
    assert joined[0]["performance_match"] is True
    assert joined[0]["performance"]["ctr"] == "6.5"


def test_packaging_associations_are_read_from_latest_run_only(tmp_path):
    db=tmp_path/"analytics.db"
    con=sqlite3.connect(db)
    con.executescript("""
    CREATE TABLE thumbnail_packaging_comparison_runs(id INTEGER PRIMARY KEY,computed_at TEXT,evidence_video_count INTEGER,association_count INTEGER,notes TEXT);
    CREATE TABLE thumbnail_packaging_associations(id INTEGER PRIMARY KEY,run_id INTEGER,computed_at TEXT,context_type TEXT,context_value TEXT,feature_name TEXT,feature_value TEXT,video_count INTEGER,total_impressions REAL,weighted_ctr REAL,comparison_video_count INTEGER,comparison_impressions REAL,comparison_weighted_ctr REAL,ctr_delta_points REAL,evidence_weight REAL,maturity TEXT,association_direction TEXT,attribution_status TEXT,interpretation TEXT,evidence_json TEXT);
    INSERT INTO thumbnail_packaging_comparison_runs VALUES(1,'old',10,1,'old');
    INSERT INTO thumbnail_packaging_comparison_runs VALUES(2,'new',20,2,'new');
    INSERT INTO thumbnail_packaging_associations VALUES(1,1,'old','channel','all','composition_layout','old_layout',10,1000,4,10,1000,4,0,1,'mature','positive','eligible','old','{}');
    INSERT INTO thumbnail_packaging_associations VALUES(2,2,'new','channel','all','composition_layout','channel_layout',20,2000,5,20,2000,4,1,1,'mature','positive','eligible','channel','{}');
    INSERT INTO thumbnail_packaging_associations VALUES(3,2,'new','hero_category','food','composition_layout','food_layout',11,1800,6,9,1200,4,2,1,'mature','positive','eligible','food','{}');
    """)
    con.commit(); con.close()
    out=V2AnalyticsReadOnlyAdapter(db).latest_packaging_associations("food")
    assert out["run"]["id"]==2
    assert [x["feature_value"] for x in out["category"]]==["food_layout"]
    assert [x["feature_value"] for x in out["channel"]]==["channel_layout"]

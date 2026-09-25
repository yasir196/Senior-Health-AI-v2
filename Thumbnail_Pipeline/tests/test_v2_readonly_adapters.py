from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from Thumbnail_Pipeline.adapters.performance import read_performance_export
from Thumbnail_Pipeline.adapters.v2_assets import V2AssetsAdapter
from Thumbnail_Pipeline.intelligence.join import join_by_asset_id


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

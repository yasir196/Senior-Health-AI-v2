from pathlib import Path
import io
from PIL import Image

import analytics_db
import thumbnail_assets


def _jpg(size=(1280, 720)):
    im = Image.new("RGB", size, (20, 30, 40))
    b = io.BytesIO(); im.save(b, format="JPEG"); return b.getvalue()


def test_thumbnail_archive_uses_permanent_video_id_and_stores_outside_db(tmp_path, monkeypatch):
    db = tmp_path / "Analytics" / "senior_health_analytics.db"
    analytics_db.init_db(db)
    aid = analytics_db.register_youtube_only_video(db, title="Test video", youtube_video_id="Ah7O9lBhErs")
    calls = []
    def fake(url, timeout=20):
        calls.append(url); return _jpg(), 1280, 720
    monkeypatch.setattr(thumbnail_assets, "_download_image", fake)
    result = thumbnail_assets.download_thumbnail_snapshot(db, aid)
    assert result["status"] == "downloaded"
    assert calls == ["https://img.youtube.com/vi/Ah7O9lBhErs/maxresdefault.jpg"]
    path = Path(result["file_path"])
    assert path.is_file()
    assert path.parent == db.parent / "youtube_assets" / aid / "thumbnails"
    row = analytics_db.latest_thumbnail_snapshot(db, aid)
    assert row["youtube_video_id"] == "Ah7O9lBhErs"
    assert row["source_variant"] == "maxresdefault"
    assert row["analysis_status"] == "pending"


def test_thumbnail_archive_does_not_duplicate_without_refresh(tmp_path, monkeypatch):
    db = tmp_path / "Analytics" / "senior_health_analytics.db"
    analytics_db.init_db(db)
    aid = analytics_db.register_youtube_only_video(db, title="Test video", youtube_video_id="Ah7O9lBhErs")
    monkeypatch.setattr(thumbnail_assets, "_download_image", lambda url, timeout=20: (_jpg(), 1280, 720))
    thumbnail_assets.download_thumbnail_snapshot(db, aid)
    second = thumbnail_assets.download_thumbnail_snapshot(db, aid)
    assert second["status"] == "existing"
    with analytics_db._db_connect(db) as con:
        assert con.execute("SELECT COUNT(*) FROM thumbnail_snapshots").fetchone()[0] == 1


def test_maxres_falls_back_to_hq(tmp_path, monkeypatch):
    db = tmp_path / "Analytics" / "senior_health_analytics.db"
    analytics_db.init_db(db)
    aid = analytics_db.register_youtube_only_video(db, title="Test video", youtube_video_id="Ah7O9lBhErs")
    def fake(url, timeout=20):
        if "maxresdefault" in url: raise RuntimeError("not available")
        return _jpg((480, 360)), 480, 360
    monkeypatch.setattr(thumbnail_assets, "_download_image", fake)
    result = thumbnail_assets.download_thumbnail_snapshot(db, aid)
    assert result["source_variant"] == "hqdefault"

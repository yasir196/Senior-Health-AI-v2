from __future__ import annotations

import hashlib
import io
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

from analytics_db import AnalyticsDBError, latest_thumbnail_snapshot, list_videos, record_thumbnail_snapshot

THUMBNAIL_VARIANTS = (
    ("maxresdefault", "https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"),
    ("hqdefault", "https://img.youtube.com/vi/{video_id}/hqdefault.jpg"),
)
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,32}$")


def _download_image(url: str, timeout: int = 20) -> tuple[bytes, int, int]:
    req = urllib.request.Request(url, headers={"User-Agent": "Senior-Health-AI/thumbnail-archive"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        if int(getattr(response, "status", 200)) != 200:
            raise RuntimeError(f"HTTP {getattr(response, 'status', 'error')}")
        data = response.read(10 * 1024 * 1024 + 1)
    if not data or len(data) > 10 * 1024 * 1024:
        raise RuntimeError("Thumbnail response is empty or unexpectedly large.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
    except Exception as exc:
        raise RuntimeError(f"Response is not a valid image: {exc}") from exc
    if width < 300 or height < 150:
        raise RuntimeError(f"Thumbnail dimensions are too small: {width}x{height}")
    return data, int(width), int(height)


def download_thumbnail_snapshot(db_path: Path, analytics_id: str, *, refresh: bool = False) -> dict[str, Any]:
    videos = {str(v.get("analytics_id")): v for v in list_videos(db_path)}
    video = videos.get(str(analytics_id))
    if not video:
        raise AnalyticsDBError(f"Unknown analytics_id: {analytics_id}")
    video_id = str(video.get("youtube_video_id") or "").strip()
    if not video_id or not _VIDEO_ID_RE.fullmatch(video_id):
        raise AnalyticsDBError("A valid permanent YouTube Video ID is required before thumbnail download.")

    current = latest_thumbnail_snapshot(db_path, analytics_id)
    if current and not refresh:
        existing = Path(str(current.get("file_path") or ""))
        if existing.is_file():
            return {"status": "existing", **current}

    errors: list[str] = []
    for variant, template in THUMBNAIL_VARIANTS:
        url = template.format(video_id=video_id)
        try:
            data, width, height = _download_image(url)
            # maxresdefault can sometimes return a generic 120x90 placeholder; size gate above rejects it.
            digest = hashlib.sha256(data).hexdigest()
            # A YouTube sync always checks the current thumbnail by Video ID,
            # but unchanged artwork must not create another snapshot/version or
            # trigger another paid vision-analysis call.
            if current and str(current.get("sha256") or "").strip().lower() == digest.lower():
                existing = Path(str(current.get("file_path") or ""))
                if existing.is_file():
                    return {"status": "unchanged", **current}

            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            asset_dir = Path(db_path).parent / "youtube_assets" / str(analytics_id) / "thumbnails"
            asset_dir.mkdir(parents=True, exist_ok=True)
            path = asset_dir / f"thumbnail_{stamp}_{variant}.jpg"
            path.write_bytes(data)
            downloaded_at = datetime.now().isoformat(timespec="seconds")
            record_thumbnail_snapshot(
                db_path, analytics_id, youtube_video_id=video_id, downloaded_at=downloaded_at,
                source_url=url, source_variant=variant, file_path=str(path.resolve()),
                width=width, height=height, sha256=digest,
            )
            return {
                "status": "downloaded", "analytics_id": analytics_id, "youtube_video_id": video_id,
                "downloaded_at": downloaded_at, "source_url": url, "source_variant": variant,
                "file_path": str(path.resolve()), "width": width, "height": height, "sha256": digest,
            }
        except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError, OSError) as exc:
            errors.append(f"{variant}: {exc}")
    raise RuntimeError("Thumbnail download failed. " + " | ".join(errors))


def download_missing_thumbnails(db_path: Path) -> dict[str, Any]:
    results = {"checked": 0, "downloaded": 0, "existing": 0, "failed": 0, "errors": []}
    for video in list_videos(db_path):
        if not str(video.get("youtube_video_id") or "").strip():
            continue
        results["checked"] += 1
        try:
            item = download_thumbnail_snapshot(db_path, str(video["analytics_id"]), refresh=False)
            results[item["status"]] = int(results.get(item["status"], 0)) + 1
        except Exception as exc:
            results["failed"] += 1
            results["errors"].append(f"{video.get('youtube_video_id')}: {exc}")
    return results


def refresh_channel_thumbnails(db_path: Path) -> dict[str, Any]:
    """Check every YouTube-linked video's current thumbnail by permanent Video ID.

    New/changed artwork is archived as a new snapshot; byte-identical artwork is
    reported as unchanged and does not create duplicate history.
    """
    results = {"checked": 0, "downloaded": 0, "unchanged": 0, "failed": 0, "errors": []}
    for video in list_videos(db_path):
        if not str(video.get("youtube_video_id") or "").strip():
            continue
        results["checked"] += 1
        try:
            item = download_thumbnail_snapshot(db_path, str(video["analytics_id"]), refresh=True)
            status = str(item.get("status") or "downloaded")
            results[status] = int(results.get(status, 0)) + 1
        except Exception as exc:
            results["failed"] += 1
            results["errors"].append(f"{video.get('youtube_video_id')}: {exc}")
    return results

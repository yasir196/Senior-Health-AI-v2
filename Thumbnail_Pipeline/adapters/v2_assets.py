from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True)
class V2Thumbnail:
    asset_id: str
    path: Path


class V2AssetsAdapter:
    """Read-only view of V2 Analytics/youtube_assets.

    This class exposes paths only. It never creates, edits, renames or deletes
    anything under the V2 root.
    """

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()
        self.assets_root = (self.repo_root / "Analytics" / "youtube_assets").resolve()

    def thumbnails(self) -> list[V2Thumbnail]:
        if not self.assets_root.exists():
            return []
        result: list[V2Thumbnail] = []
        for asset_dir in sorted(p for p in self.assets_root.iterdir() if p.is_dir()):
            thumbs = asset_dir / "thumbnails"
            if not thumbs.is_dir():
                continue
            for path in sorted(thumbs.iterdir()):
                if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                    result.append(V2Thumbnail(asset_id=asset_dir.name, path=path))
        return result

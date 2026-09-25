from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class V2AnalyticsReadOnlyAdapter:
    """Read the existing V2 analytics SQLite DB without mutating it."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        if not self.db_path.is_file():
            raise FileNotFoundError(self.db_path)
        uri = f"file:{self.db_path.resolve().as_posix()}?mode=ro"
        con = sqlite3.connect(uri, uri=True)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA query_only=ON")
        return con

    def latest_thumbnail_evidence(self) -> list[dict[str, Any]]:
        """Return latest joined thumbnail/CTR evidence per analytics video.

        Uses V2's existing attribution-aware thumbnail_ctr_evidence rather than
        pretending every historical snapshot owns the video's lifetime CTR.
        """
        sql = """
        SELECT e.id AS evidence_id,e.analytics_id,e.youtube_video_id,
               e.ctr_percent AS ctr,e.impressions,e.metric_source,e.metric_snapshot_at,
               e.metric_start_date,e.metric_end_date,e.metric_days,e.attribution_status,
               e.attribution_note,e.evidence_weight,
               a.thumbnail_text,a.text_word_count,a.text_line_count,a.text_style,
               a.presenter_present,a.presenter_position,a.presenter_size,a.expression,a.gaze_target,
               a.hero_subject,a.hero_category,a.hero_count,a.question_hook,a.number_hook,
               a.arrow_present,a.arrow_target,a.background_style,a.background_brightness,
               a.background_color_family,a.dominant_palette,a.text_color_scheme,a.accent_color_family,
               a.palette_temperature,a.contrast_level,a.visual_complexity,a.major_visual_object_count,
               a.composition_layout,a.subject_separation,a.curiosity_mechanism,
               a.title_thumbnail_relationship,a.semantic_summary,a.confidence,a.features_json,
               s.id AS thumbnail_snapshot_id,s.downloaded_at,s.file_path AS thumbnail_path,s.sha256,
               COALESCE(NULLIF(v.youtube_title,''),NULLIF(v.locked_title,''),v.project_slug,v.analytics_id) AS title,
               v.publish_date,v.publish_weekday
        FROM thumbnail_ctr_evidence e
        JOIN thumbnail_analyses a ON a.id=e.thumbnail_analysis_id
        JOIN thumbnail_snapshots s ON s.id=e.thumbnail_snapshot_id
        JOIN videos v ON v.analytics_id=e.analytics_id
        WHERE e.id=(
            SELECT e2.id FROM thumbnail_ctr_evidence e2
            WHERE e2.analytics_id=e.analytics_id
            ORDER BY e2.joined_at DESC,e2.id DESC LIMIT 1
        )
          AND e.ctr_percent IS NOT NULL AND e.impressions IS NOT NULL AND e.impressions>0
        ORDER BY e.analytics_id
        """
        with self._connect() as con:
            return [dict(r) for r in con.execute(sql).fetchall()]

    def to_intelligence_rows(self) -> list[dict[str, Any]]:
        out=[]
        for r in self.latest_thumbnail_evidence():
            out.append({
                "asset_id": r["analytics_id"],
                "thumbnail_path": r["thumbnail_path"],
                "performance": {
                    "video_id": r["youtube_video_id"], "title": r["title"],
                    "ctr": r["ctr"], "impressions": r["impressions"],
                    "upload_date": r["publish_date"],
                    "metric_source": r["metric_source"],
                    "attribution_status": r["attribution_status"],
                    "evidence_weight": r["evidence_weight"],
                },
                "ocr": {
                    "text": r["thumbnail_text"],
                    "word_count": r["text_word_count"],
                    "line_count": r["text_line_count"],
                },
                "v2_analysis": {k:r[k] for k in (
                    "presenter_present","presenter_position","presenter_size","expression","gaze_target",
                    "hero_subject","hero_category","hero_count","text_style","question_hook","number_hook",
                    "background_style","background_brightness","dominant_palette","text_color_scheme",
                    "accent_color_family","contrast_level","visual_complexity","major_visual_object_count",
                    "composition_layout","subject_separation","curiosity_mechanism",
                    "title_thumbnail_relationship","confidence"
                )},
                "attribution": {
                    "status": r["attribution_status"], "note": r["attribution_note"],
                    "metric_start_date": r["metric_start_date"], "metric_end_date": r["metric_end_date"],
                    "metric_days": r["metric_days"],
                },
            })
        return out

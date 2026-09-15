from __future__ import annotations

import csv
import io
import json
import re
from difflib import SequenceMatcher
import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


SCHEMA_VERSION = 11
RETENTION_MAPPING_CACHE_VERSION = 1
TRANSCRIPT_OVERLAP_CLEANUP_VERSION = 1


class AnalyticsDBError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _db_connect(db_path: Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # Streamlit reruns the script on every interaction and long imports (YouTube
    # sync, bulk CSV, thumbnail learning) hold write transactions. Without WAL and
    # a busy timeout, concurrent reruns raise "database is locked".
    con = sqlite3.connect(db_path, timeout=30.0, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 30000")
    try:
        con.execute("PRAGMA journal_mode = WAL")
        con.execute("PRAGMA synchronous = NORMAL")
    except sqlite3.DatabaseError:
        # Read-only media or a network path cannot switch journal modes; the
        # default rollback journal still works, just with less concurrency.
        pass
    return con


def init_db(db_path: Path) -> None:
    with _db_connect(db_path) as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS videos (
                analytics_id TEXT PRIMARY KEY,
                project_id TEXT,
                project_slug TEXT,
                project_path_at_creation TEXT,
                source_type TEXT NOT NULL DEFAULT 'project',
                locked_title TEXT,
                youtube_title TEXT,
                youtube_video_id TEXT,
                publish_date TEXT,
                publish_weekday TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                project_folder_status TEXT NOT NULL DEFAULT 'available',
                timeline_status TEXT NOT NULL DEFAULT 'pending',
                timeline_source TEXT,
                analytics_status TEXT NOT NULL DEFAULT 'pending',
                retention_status TEXT NOT NULL DEFAULT 'pending',
                comments_status TEXT NOT NULL DEFAULT 'pending',
                notes TEXT
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_videos_project_id
            ON videos(project_id) WHERE project_id IS NOT NULL;

            CREATE UNIQUE INDEX IF NOT EXISTS idx_videos_youtube_id
            ON videos(youtube_video_id) WHERE youtube_video_id IS NOT NULL AND youtube_video_id <> '';

            CREATE TABLE IF NOT EXISTS scene_snapshots (
                analytics_id TEXT NOT NULL,
                scene_id TEXT NOT NULL,
                start_sec REAL,
                end_sec REAL,
                duration_sec REAL,
                script_text TEXT,
                visual_mode TEXT,
                asset_type TEXT,
                overlay_type TEXT,
                avatar_chunk TEXT,
                timing_source TEXT,
                source TEXT NOT NULL,
                ordinal INTEGER,
                PRIMARY KEY (analytics_id, scene_id, source),
                FOREIGN KEY (analytics_id) REFERENCES videos(analytics_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS thumbnail_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analytics_id TEXT NOT NULL,
                youtube_video_id TEXT NOT NULL,
                downloaded_at TEXT NOT NULL,
                source_url TEXT NOT NULL,
                source_variant TEXT NOT NULL,
                file_path TEXT NOT NULL,
                width INTEGER,
                height INTEGER,
                sha256 TEXT,
                is_current INTEGER NOT NULL DEFAULT 1,
                analysis_status TEXT NOT NULL DEFAULT 'pending',
                FOREIGN KEY (analytics_id) REFERENCES videos(analytics_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_thumbnail_snapshots_analytics
            ON thumbnail_snapshots(analytics_id, downloaded_at);

            CREATE TABLE IF NOT EXISTS thumbnail_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thumbnail_snapshot_id INTEGER NOT NULL UNIQUE,
                analytics_id TEXT NOT NULL,
                youtube_video_id TEXT NOT NULL,
                analyzed_at TEXT NOT NULL,
                model TEXT NOT NULL,
                title_at_analysis TEXT,
                presenter_present INTEGER,
                presenter_position TEXT,
                presenter_size TEXT,
                expression TEXT,
                gaze_target TEXT,
                hero_subject TEXT,
                hero_category TEXT,
                hero_count INTEGER,
                thumbnail_text TEXT,
                text_word_count INTEGER,
                text_line_count INTEGER,
                text_style TEXT,
                question_hook INTEGER,
                number_hook INTEGER,
                arrow_present INTEGER,
                arrow_target TEXT,
                background_style TEXT,
                background_brightness TEXT,
                background_color_family TEXT,
                dominant_palette TEXT,
                text_color_scheme TEXT,
                accent_color_family TEXT,
                palette_temperature TEXT,
                contrast_level TEXT,
                visual_complexity TEXT,
                major_visual_object_count INTEGER,
                composition_layout TEXT,
                subject_separation TEXT,
                curiosity_mechanism TEXT,
                title_thumbnail_relationship TEXT,
                semantic_summary TEXT,
                confidence REAL,
                features_json TEXT NOT NULL,
                raw_response TEXT,
                FOREIGN KEY (thumbnail_snapshot_id) REFERENCES thumbnail_snapshots(id) ON DELETE CASCADE,
                FOREIGN KEY (analytics_id) REFERENCES videos(analytics_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_thumbnail_analyses_analytics
            ON thumbnail_analyses(analytics_id, analyzed_at);

            CREATE TABLE IF NOT EXISTS thumbnail_ctr_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thumbnail_snapshot_id INTEGER NOT NULL,
                thumbnail_analysis_id INTEGER NOT NULL,
                analytics_id TEXT NOT NULL,
                youtube_video_id TEXT NOT NULL,
                joined_at TEXT NOT NULL,
                ctr_percent REAL,
                impressions REAL,
                metric_source TEXT NOT NULL,
                metric_snapshot_at TEXT,
                metric_start_date TEXT,
                metric_end_date TEXT,
                metric_days INTEGER,
                attribution_status TEXT NOT NULL,
                attribution_note TEXT,
                evidence_weight REAL,
                UNIQUE(thumbnail_snapshot_id, thumbnail_analysis_id, metric_source),
                FOREIGN KEY (thumbnail_snapshot_id) REFERENCES thumbnail_snapshots(id) ON DELETE CASCADE,
                FOREIGN KEY (thumbnail_analysis_id) REFERENCES thumbnail_analyses(id) ON DELETE CASCADE,
                FOREIGN KEY (analytics_id) REFERENCES videos(analytics_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_thumbnail_ctr_evidence_analytics
            ON thumbnail_ctr_evidence(analytics_id, joined_at);

            CREATE TABLE IF NOT EXISTS thumbnail_packaging_comparison_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                computed_at TEXT NOT NULL,
                evidence_video_count INTEGER NOT NULL DEFAULT 0,
                association_count INTEGER NOT NULL DEFAULT 0,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS thumbnail_packaging_associations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                computed_at TEXT NOT NULL,
                context_type TEXT NOT NULL,
                context_value TEXT NOT NULL,
                feature_name TEXT NOT NULL,
                feature_value TEXT NOT NULL,
                video_count INTEGER NOT NULL,
                total_impressions REAL NOT NULL DEFAULT 0,
                weighted_ctr REAL,
                comparison_video_count INTEGER NOT NULL DEFAULT 0,
                comparison_impressions REAL NOT NULL DEFAULT 0,
                comparison_weighted_ctr REAL,
                ctr_delta_points REAL,
                evidence_weight REAL,
                maturity TEXT NOT NULL,
                association_direction TEXT NOT NULL,
                attribution_status TEXT NOT NULL,
                interpretation TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES thumbnail_packaging_comparison_runs(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_thumbnail_packaging_assoc_run
            ON thumbnail_packaging_associations(run_id, context_type, context_value);

            CREATE INDEX IF NOT EXISTS idx_thumbnail_packaging_assoc_feature
            ON thumbnail_packaging_associations(feature_name, feature_value, maturity);

            CREATE TABLE IF NOT EXISTS channel_packaging_rules (
                rule_key TEXT PRIMARY KEY,
                context_type TEXT NOT NULL,
                context_value TEXT NOT NULL,
                feature_name TEXT NOT NULL,
                feature_value TEXT NOT NULL,
                direction TEXT NOT NULL,
                guidance_text TEXT NOT NULL,
                status TEXT NOT NULL,
                source_run_id INTEGER,
                source_association_id INTEGER,
                videos INTEGER NOT NULL DEFAULT 0,
                total_impressions REAL NOT NULL DEFAULT 0,
                weighted_ctr REAL,
                comparison_weighted_ctr REAL,
                ctr_delta_points REAL,
                evidence_weight REAL,
                attribution_status TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                activated_at TEXT,
                retired_at TEXT,
                reviewed_at TEXT,
                review_note TEXT,
                evidence_json TEXT NOT NULL,
                FOREIGN KEY (source_run_id) REFERENCES thumbnail_packaging_comparison_runs(id) ON DELETE SET NULL,
                FOREIGN KEY (source_association_id) REFERENCES thumbnail_packaging_associations(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_channel_packaging_rules_status
            ON channel_packaging_rules(status, context_type, context_value);

            CREATE TABLE IF NOT EXISTS performance_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analytics_id TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                report_kind TEXT NOT NULL,
                source_file TEXT,
                date_range_label TEXT,
                views REAL,
                engaged_views REAL,
                watch_time_hours REAL,
                average_view_duration_seconds REAL,
                average_percentage_viewed REAL,
                impressions REAL,
                ctr_percent REAL,
                subscribers REAL,
                average_views_per_viewer REAL,
                unique_viewers REAL,
                unique_reach REAL,
                new_viewers REAL,
                returning_viewers REAL,
                casual_viewers REAL,
                regular_viewers REAL,
                stayed_to_watch_percent REAL,
                raw_json TEXT,
                FOREIGN KEY (analytics_id) REFERENCES videos(analytics_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS traffic_source_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analytics_id TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                source_file TEXT,
                traffic_source TEXT,
                views REAL,
                engaged_views REAL,
                watch_time_hours REAL,
                average_view_duration_seconds REAL,
                average_percentage_viewed REAL,
                impressions REAL,
                ctr_percent REAL,
                raw_json TEXT,
                FOREIGN KEY (analytics_id) REFERENCES videos(analytics_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS daily_series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analytics_id TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                series_type TEXT NOT NULL,
                source_file TEXT,
                date TEXT,
                traffic_source TEXT,
                engaged_views REAL,
                views REAL,
                watch_time_hours REAL,
                raw_json TEXT,
                FOREIGN KEY (analytics_id) REFERENCES videos(analytics_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS reach_daily (
                analytics_id TEXT NOT NULL,
                report_date TEXT NOT NULL,
                impressions REAL,
                ctr_percent REAL,
                report_id TEXT,
                report_create_time TEXT,
                source_file TEXT,
                imported_at TEXT NOT NULL,
                PRIMARY KEY (analytics_id, report_date),
                FOREIGN KEY (analytics_id) REFERENCES videos(analytics_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS reporting_reports (
                job_id TEXT NOT NULL,
                report_id TEXT NOT NULL,
                report_type_id TEXT,
                start_time TEXT,
                end_time TEXT,
                create_time TEXT,
                processed_at TEXT NOT NULL,
                PRIMARY KEY (job_id, report_id)
            );

            CREATE TABLE IF NOT EXISTS retention_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analytics_id TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                source_file TEXT,
                time_sec REAL,
                position_percent REAL,
                retention_percent REAL,
                FOREIGN KEY (analytics_id) REFERENCES videos(analytics_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS retention_mapping_cache (
                analytics_id TEXT NOT NULL,
                scene_id TEXT NOT NULL,
                source TEXT,
                start_sec REAL,
                end_sec REAL,
                duration_sec REAL,
                script_text TEXT,
                visual_mode TEXT,
                asset_type TEXT,
                overlay_type TEXT,
                retention_start REAL,
                retention_end REAL,
                retention_avg REAL,
                retention_delta REAL,
                retention_signal TEXT,
                problem_score REAL,
                cache_version INTEGER NOT NULL,
                computed_at TEXT NOT NULL,
                ordinal INTEGER,
                PRIMARY KEY (analytics_id, scene_id, source),
                FOREIGN KEY (analytics_id) REFERENCES videos(analytics_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_retention_mapping_cache_analytics
            ON retention_mapping_cache(analytics_id, ordinal);

            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analytics_id TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                source_file TEXT,
                comment_id TEXT,
                author TEXT,
                published_at TEXT,
                likes REAL,
                text TEXT,
                raw_json TEXT,
                FOREIGN KEY (analytics_id) REFERENCES videos(analytics_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS production_learning_scenes (
                analytics_id TEXT NOT NULL,
                scene_id TEXT NOT NULL,
                start_sec REAL NOT NULL,
                end_sec REAL NOT NULL,
                duration_sec REAL,
                script_text TEXT,
                visual_mode TEXT,
                asset_type TEXT,
                overlay_type TEXT,
                retention_start REAL,
                retention_end REAL,
                retention_avg REAL,
                retention_delta REAL,
                retention_signal TEXT,
                evidence_status TEXT NOT NULL DEFAULT 'OBSERVATION',
                source TEXT NOT NULL DEFAULT 'actual_timeline_retention',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (analytics_id, scene_id),
                FOREIGN KEY (analytics_id) REFERENCES videos(analytics_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_production_learning_asset
            ON production_learning_scenes(asset_type, visual_mode, retention_signal);

            CREATE TABLE IF NOT EXISTS channel_script_rules (
                rule_key TEXT PRIMARY KEY,
                script_pattern TEXT NOT NULL,
                rule_text TEXT NOT NULL,
                status TEXT NOT NULL,
                videos INTEGER NOT NULL DEFAULT 0,
                events INTEGER NOT NULL DEFAULT 0,
                avg_drop REAL,
                median_drop REAL,
                opening_videos INTEGER NOT NULL DEFAULT 0,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                activated_at TEXT,
                retired_at TEXT,
                evidence_json TEXT
            );
            """
        )
        # Forward-compatible migration for databases created before publish_weekday existed.
        video_cols = {row["name"] for row in con.execute("PRAGMA table_info(videos)").fetchall()}
        if "publish_weekday" not in video_cols:
            con.execute("ALTER TABLE videos ADD COLUMN publish_weekday TEXT")

        # Stage 2 thumbnail-analysis migration. Preserve all existing rows and add
        # queryable fields required for reliable packaging feature extraction.
        analysis_cols = {row["name"] for row in con.execute("PRAGMA table_info(thumbnail_analyses)").fetchall()}
        for column_name, column_type in (
            ("hero_category", "TEXT"),
            ("background_brightness", "TEXT"),
            ("major_visual_object_count", "INTEGER"),
            ("composition_layout", "TEXT"),
            ("subject_separation", "TEXT"),
            ("background_color_family", "TEXT"),
            ("dominant_palette", "TEXT"),
            ("text_color_scheme", "TEXT"),
            ("accent_color_family", "TEXT"),
            ("palette_temperature", "TEXT"),
            ("contrast_level", "TEXT"),
        ):
            if column_name not in analysis_cols:
                con.execute(f"ALTER TABLE thumbnail_analyses ADD COLUMN {column_name} {column_type}")

        con.execute(
            "INSERT INTO meta(key,value) VALUES('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(SCHEMA_VERSION),),
        )


def _archive_project_analytics_assets(db_path: Path, analytics_id: str, project_path: Path) -> int:
    """Copy analytics-critical project files into Analytics without changing project paths."""
    project_path = Path(project_path)
    archive_dir = Path(db_path).parent / "project_assets" / str(analytics_id)
    copied = 0
    for filename in ("06_final_script.md", "07_production_sheet.csv", "08_actual_timeline.csv", "production_timeline_snapshot.csv"):
        source = project_path / filename
        if not source.is_file():
            continue
        archive_dir.mkdir(parents=True, exist_ok=True)
        destination = archive_dir / filename
        try:
            if (not destination.is_file() or
                    source.stat().st_size != destination.stat().st_size or
                    source.read_bytes() != destination.read_bytes()):
                shutil.copy2(source, destination)
            copied += 1
        except OSError:
            # Archiving must never break the production workflow.
            continue
    return copied


def _project_payload(project_path: Path) -> dict[str, Any]:
    path = Path(project_path) / "project.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            return {}


def ensure_project_record(db_path: Path, project_path: Path, *, title: str | None = None) -> str:
    """Create or refresh a permanent analytics record for a local project."""
    init_db(db_path)
    project_path = Path(project_path)
    payload = _project_payload(project_path)
    project_id = str(payload.get("project_id") or "").strip()
    if not project_id:
        # Stable enough for legacy projects without mutating their project.json.
        seed = f"{project_path.name}|{payload.get('created_at','')}|{payload.get('anchor_title','')}"
        project_id = str(uuid.uuid5(uuid.NAMESPACE_URL, seed))
    locked_title = str(title or payload.get("anchor_title") or payload.get("topic") or project_path.name).strip()
    created_at = str(payload.get("created_at") or _now())

    with _db_connect(db_path) as con:
        row = con.execute("SELECT analytics_id FROM videos WHERE project_id=?", (project_id,)).fetchone()
        if row:
            analytics_id = row["analytics_id"]
            con.execute(
                """
                UPDATE videos
                SET project_slug=?, project_path_at_creation=?, locked_title=?,
                    project_folder_status='available', updated_at=?
                WHERE analytics_id=?
                """,
                (project_path.name, str(project_path), locked_title, _now(), analytics_id),
            )
            _archive_project_analytics_assets(db_path, analytics_id, project_path)
            return analytics_id

        analytics_id = str(uuid.uuid4())
        con.execute(
            """
            INSERT INTO videos(
                analytics_id, project_id, project_slug, project_path_at_creation, source_type,
                locked_title, created_at, updated_at, project_folder_status, timeline_status,
                analytics_status, retention_status, comments_status
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                analytics_id, project_id, project_path.name, str(project_path), "project",
                locked_title, created_at, _now(), "available", "pending",
                "pending", "pending", "pending",
            ),
        )
        _archive_project_analytics_assets(db_path, analytics_id, project_path)
        return analytics_id



def _normalized_title(value: Any) -> str:
    """Conservative title key used only for exact normalized auto-linking."""
    s = str(value or "").casefold()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def auto_link_existing_projects(db_path: Path, projects_dir: Path) -> dict[str, int]:
    """Register/refresh local projects without guessing a YouTube identity.

    A local project and a YouTube video are intentionally kept separate until the
    operator explicitly binds a YouTube Video ID to the project's analytics_id.
    Titles, fuzzy similarity, duration, and dates are never used here to create a
    permanent YouTube/project identity link.
    """
    init_db(db_path)
    projects_dir = Path(projects_dir)
    result = {"scanned": 0, "linked": 0, "registered": 0, "timelines": 0, "ambiguous": 0}
    if not projects_dir.is_dir():
        return result

    for project_path in sorted((x for x in projects_dir.iterdir() if x.is_dir()), key=lambda x: x.name.lower()):
        payload = _project_payload(project_path)
        if not payload and not (project_path / "08_actual_timeline.csv").is_file():
            continue
        result["scanned"] += 1
        before = None
        project_id = str(payload.get("project_id") or "").strip()
        if project_id:
            with _db_connect(db_path) as con:
                before = con.execute("SELECT analytics_id FROM videos WHERE project_id=?", (project_id,)).fetchone()
        aid = ensure_project_record(db_path, project_path)
        if before is None:
            result["registered"] += 1

        timeline = project_path / "08_actual_timeline.csv"
        if timeline.is_file():
            try:
                snapshot_actual_timeline(db_path, aid, timeline, production_sheet_path=project_path / "07_production_sheet.csv")
                result["timelines"] += 1
            except Exception:
                pass
        _archive_project_analytics_assets(db_path, aid, project_path)
    return result

def register_youtube_only_video(
    db_path: Path,
    *,
    title: str,
    youtube_video_id: str | None = None,
    publish_date: str | None = None,
    notes: str | None = None,
) -> str:
    init_db(db_path)
    title = str(title or "").strip()
    if not title:
        raise AnalyticsDBError("YouTube title is required.")
    video_id = str(youtube_video_id or "").strip() or None

    with _db_connect(db_path) as con:
        if video_id:
            row = con.execute("SELECT analytics_id FROM videos WHERE youtube_video_id=?", (video_id,)).fetchone()
            if row:
                con.execute(
                    "UPDATE videos SET youtube_title=?, publish_date=COALESCE(?, publish_date), updated_at=? WHERE analytics_id=?",
                    (title, publish_date, _now(), row["analytics_id"]),
                )
                return row["analytics_id"]

        analytics_id = str(uuid.uuid4())
        con.execute(
            """
            INSERT INTO videos(
                analytics_id, source_type, youtube_title, youtube_video_id, publish_date,
                created_at, updated_at, project_folder_status, timeline_status,
                analytics_status, retention_status, comments_status, notes
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                analytics_id, "youtube_only", title, video_id, publish_date or None,
                _now(), _now(), "not_available", "unavailable",
                "pending", "pending", "pending", notes or None,
            ),
        )
        return analytics_id


def update_video_identity(
    db_path: Path,
    analytics_id: str,
    *,
    youtube_title: str | None = None,
    youtube_video_id: str | None = None,
    publish_date: str | None = None,
    publish_weekday: str | None = None,
) -> None:
    with _db_connect(db_path) as con:
        if youtube_video_id:
            existing = con.execute(
                "SELECT analytics_id FROM videos WHERE youtube_video_id=? AND analytics_id<>?",
                (youtube_video_id.strip(), analytics_id),
            ).fetchone()
            if existing:
                raise AnalyticsDBError("That YouTube Video ID is already linked to another analytics record.")
        con.execute(
            """
            UPDATE videos
            SET youtube_title=COALESCE(NULLIF(?,''), youtube_title),
                youtube_video_id=COALESCE(NULLIF(?,''), youtube_video_id),
                publish_date=COALESCE(NULLIF(?,''), publish_date),
                publish_weekday=COALESCE(NULLIF(?,''), publish_weekday),
                updated_at=?
            WHERE analytics_id=?
            """,
            (
                youtube_title or "",
                youtube_video_id or "",
                publish_date or "",
                publish_weekday or "",
                _now(),
                analytics_id,
            ),
        )


def _parse_time(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not pd.isna(value):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        pass
    parts = s.split(":")
    try:
        nums = [float(p) for p in parts]
    except Exception:
        return None
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    return None


def _col(row: dict[str, Any], aliases: list[str]) -> Any:
    norm = {re.sub(r"[^a-z0-9]+", "", str(k).lower()): v for k, v in row.items()}
    for alias in aliases:
        key = re.sub(r"[^a-z0-9]+", "", alias.lower())
        if key in norm:
            return norm[key]
    return None


def _invalidate_retention_mapping_cache(db_path: Path, analytics_id: str) -> None:
    """Invalidate only the derived scene-retention cache for one video."""
    init_db(db_path)
    with _db_connect(db_path) as con:
        con.execute("DELETE FROM retention_mapping_cache WHERE analytics_id=?", (analytics_id,))


def _retention_mapping_cache_df(db_path: Path, analytics_id: str) -> pd.DataFrame:
    """Return a valid permanent SQLite mapping cache, or an empty DataFrame."""
    init_db(db_path)
    with _db_connect(db_path) as con:
        rows = con.execute(
            """
            SELECT scene_id,source,start_sec,end_sec,duration_sec,script_text,visual_mode,asset_type,
                   overlay_type,retention_start,retention_end,retention_avg,retention_delta,
                   retention_signal,problem_score,ordinal,cache_version
            FROM retention_mapping_cache
            WHERE analytics_id=? AND cache_version=?
            ORDER BY ordinal,start_sec
            """,
            (analytics_id, RETENTION_MAPPING_CACHE_VERSION),
        ).fetchall()
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame([dict(r) for r in rows])
    if "cache_version" in out.columns:
        out = out.drop(columns=["cache_version"])
    return out


def _store_retention_mapping_cache(db_path: Path, analytics_id: str, mapped: pd.DataFrame) -> None:
    """Persist the derived scene-retention mapping so normal tab opens are read-only and fast."""
    if mapped is None or mapped.empty:
        return
    computed_at = _now()
    rows = []
    for ordinal, (_, r) in enumerate(mapped.sort_values("start_sec").iterrows(), start=1):
        rows.append((
            analytics_id, str(r.get("scene_id") or ""), r.get("source"),
            _num(r.get("start_sec")), _num(r.get("end_sec")), _num(r.get("duration_sec")),
            str(r.get("script_text") or ""), r.get("visual_mode"), r.get("asset_type"),
            r.get("overlay_type"), _num(r.get("retention_start")), _num(r.get("retention_end")),
            _num(r.get("retention_avg")), _num(r.get("retention_delta")),
            str(r.get("retention_signal") or ""), _num(r.get("problem_score")),
            RETENTION_MAPPING_CACHE_VERSION, computed_at, ordinal,
        ))
    with _db_connect(db_path) as con:
        con.execute("DELETE FROM retention_mapping_cache WHERE analytics_id=?", (analytics_id,))
        con.executemany(
            """
            INSERT INTO retention_mapping_cache(
                analytics_id,scene_id,source,start_sec,end_sec,duration_sec,script_text,visual_mode,
                asset_type,overlay_type,retention_start,retention_end,retention_avg,retention_delta,
                retention_signal,problem_score,cache_version,computed_at,ordinal
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            rows,
        )


def snapshot_actual_timeline(
    db_path: Path,
    analytics_id: str,
    timeline_path: Path,
    *,
    production_sheet_path: Path | None = None,
) -> int:
    init_db(db_path)
    timeline_path = Path(timeline_path)
    if not timeline_path.is_file():
        raise AnalyticsDBError("08_actual_timeline.csv is missing.")

    tdf = pd.read_csv(timeline_path)
    pdf = None
    if production_sheet_path and Path(production_sheet_path).is_file():
        try:
            pdf = pd.read_csv(production_sheet_path)
        except Exception:
            pdf = None

    prod_by_scene: dict[str, dict[str, Any]] = {}
    if pdf is not None:
        for _, prow in pdf.iterrows():
            d = prow.to_dict()
            sid = str(_col(d, ["scene_id", "Scene ID"]) or "").strip()
            if sid:
                prod_by_scene[sid] = d

    rows: list[tuple] = []
    for idx, r in tdf.iterrows():
        d = r.to_dict()
        scene_id = str(_col(d, ["Scene ID", "scene_id"]) or f"S{idx+1:03d}").strip()
        start = _parse_time(_col(d, ["Actual Audio Start", "start_time", "Start", "actual_start"]))
        end = _parse_time(_col(d, ["Actual Audio End", "end_time", "End", "actual_end"]))
        duration = _parse_time(_col(d, ["Duration", "duration_sec"]))
        if duration is None and start is not None and end is not None:
            duration = max(0.0, end - start)
        script = str(_col(d, ["Script Text", "script_excerpt", "narration", "script_text"]) or "").strip()

        p = prod_by_scene.get(scene_id, {})
        visual_mode = str(_col(p, ["visual_mode", "Visual Mode"]) or "").strip() or None
        asset_type = str(_col(p, ["recommended_asset_type", "asset_type", "asset_status", "Asset Type"]) or "").strip() or None
        overlay_type = str(_col(p, ["overlay_type", "Overlay Type"]) or "").strip() or None
        avatar_chunk = str(_col(d, ["Avatar Chunk", "avatar_chunk"]) or "").strip() or None
        timing_source = str(_col(d, ["Timing Source", "timing_source"]) or "").strip() or None
        rows.append((
            analytics_id, scene_id, start, end, duration, script, visual_mode,
            asset_type, overlay_type, avatar_chunk, timing_source, "actual_timeline", idx + 1
        ))

    with _db_connect(db_path) as con:
        con.execute("DELETE FROM scene_snapshots WHERE analytics_id=? AND source='actual_timeline'", (analytics_id,))
        con.executemany(
            """
            INSERT INTO scene_snapshots(
                analytics_id, scene_id, start_sec, end_sec, duration_sec, script_text,
                visual_mode, asset_type, overlay_type, avatar_chunk, timing_source, source, ordinal
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            rows,
        )
        con.execute(
            """
            UPDATE videos SET timeline_status='ready', timeline_source='actual_timeline',
            project_folder_status='available', updated_at=? WHERE analytics_id=?
            """,
            (_now(), analytics_id),
        )
    _invalidate_retention_mapping_cache(db_path, analytics_id)
    _archive_project_analytics_assets(db_path, analytics_id, timeline_path.parent)
    return len(rows)


def build_production_timeline_snapshot(
    timeline_path: Path,
    production_sheet_path: Path,
    output_path: Path,
) -> pd.DataFrame:
    """Merge final production metadata onto authoritative Actual Timeline timing.

    Scene ID is the only automatic join key. Production-sheet planned timing is
    retained only as prefixed reference metadata; learning timing always comes
    from 08_actual_timeline.csv.
    """
    timeline_path = Path(timeline_path)
    production_sheet_path = Path(production_sheet_path)
    output_path = Path(output_path)
    if not timeline_path.is_file():
        raise AnalyticsDBError("08_actual_timeline.csv is missing.")
    if not production_sheet_path.is_file():
        raise AnalyticsDBError("07_production_sheet.csv is missing.")

    tdf = pd.read_csv(timeline_path)
    pdf = pd.read_csv(production_sheet_path)

    def scene_col(df: pd.DataFrame, label: str) -> str:
        for candidate in ("Scene ID", "scene_id"):
            if candidate in df.columns:
                return candidate
        raise AnalyticsDBError(f"{label} is missing Scene ID.")

    t_scene = scene_col(tdf, "08_actual_timeline.csv")
    p_scene = scene_col(pdf, "07_production_sheet.csv")

    t_ids = tdf[t_scene].fillna("").astype(str).str.strip()
    p_ids = pdf[p_scene].fillna("").astype(str).str.strip()
    if (t_ids == "").any():
        raise AnalyticsDBError("08_actual_timeline.csv contains an empty Scene ID.")
    if (p_ids == "").any():
        raise AnalyticsDBError("07_production_sheet.csv contains an empty Scene ID.")
    if t_ids.duplicated().any():
        dup = t_ids[t_ids.duplicated()].iloc[0]
        raise AnalyticsDBError(f"08_actual_timeline.csv contains duplicate Scene ID: {dup}")
    if p_ids.duplicated().any():
        dup = p_ids[p_ids.duplicated()].iloc[0]
        raise AnalyticsDBError(f"07_production_sheet.csv contains duplicate Scene ID: {dup}")

    prod_map = {
        str(row[p_scene]).strip(): row.to_dict()
        for _, row in pdf.iterrows()
    }

    rows: list[dict[str, Any]] = []
    unmatched: list[str] = []
    for ordinal, (_, trow) in enumerate(tdf.iterrows(), start=1):
        td = trow.to_dict()
        sid = str(td.get(t_scene) or "").strip()
        pdict = prod_map.get(sid)
        if pdict is None:
            unmatched.append(sid)
            continue

        actual_start = _parse_time(_col(td, ["Actual Audio Start", "start_time", "Start", "actual_start"]))
        actual_end = _parse_time(_col(td, ["Actual Audio End", "end_time", "End", "actual_end"]))
        actual_duration = _parse_time(_col(td, ["Duration", "duration_sec"]))
        if actual_start is None or actual_end is None:
            raise AnalyticsDBError(f"08_actual_timeline.csv has invalid/missing actual timing for Scene ID: {sid}")
        if actual_duration is None:
            actual_duration = max(0.0, actual_end - actual_start)

        merged: dict[str, Any] = {
            "scene_id": sid,
            "actual_start_sec": float(actual_start),
            "actual_end_sec": float(actual_end),
            "actual_duration_sec": float(actual_duration),
            "timing_authority": "08_actual_timeline.csv",
            "ordinal": ordinal,
        }

        # Keep the complete Actual Timeline row for auditability.
        for key, value in td.items():
            if key not in (t_scene,):
                merged[f"timeline_{key}"] = value

        # Keep complete production metadata, but prefix it so planned timing can
        # never be confused with authoritative actual timing.
        for key, value in pdict.items():
            if key not in (p_scene,):
                merged[f"production_{key}"] = value

        rows.append(merged)

    if unmatched:
        preview = ", ".join(unmatched[:8])
        suffix = "..." if len(unmatched) > 8 else ""
        raise AnalyticsDBError(
            f"Production/Actual Timeline Scene ID mismatch: {len(unmatched)} Actual Timeline scene(s) "
            f"have no Production Sheet row ({preview}{suffix}). Snapshot was not written."
        )

    snapshot = pd.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    snapshot.to_csv(tmp, index=False)
    tmp.replace(output_path)
    return snapshot


def archive_production_learning_checkpoint(
    db_path: Path,
    project_path: Path,
) -> dict[str, Any]:
    """SEO-time final production archive for future production learning."""
    db_path = Path(db_path)
    project_path = Path(project_path)
    analytics_id = ensure_project_record(db_path, project_path)

    timeline = project_path / "08_actual_timeline.csv"
    production = project_path / "07_production_sheet.csv"
    if not timeline.is_file():
        raise AnalyticsDBError("SEO production archive requires 08_actual_timeline.csv.")
    if not production.is_file():
        raise AnalyticsDBError("SEO production archive requires 07_production_sheet.csv.")

    archive_dir = db_path.parent / "project_assets" / str(analytics_id)
    archive_dir.mkdir(parents=True, exist_ok=True)
    merged_path = archive_dir / "production_timeline_snapshot.csv"

    snapshot = build_production_timeline_snapshot(timeline, production, merged_path)

    # Refresh SQLite scene rows from authoritative actual timing + final
    # production metadata. This also invalidates retention mapping cache.
    scene_count = snapshot_actual_timeline(
        db_path,
        analytics_id,
        timeline,
        production_sheet_path=production,
    )

    # snapshot_actual_timeline archives project assets; explicitly copy the
    # merged canonical snapshot afterwards because it lives in Analytics.
    for filename in ("06_final_script.md", "07_production_sheet.csv", "08_actual_timeline.csv"):
        source = project_path / filename
        if source.is_file():
            shutil.copy2(source, archive_dir / filename)

    return {
        "analytics_id": analytics_id,
        "scene_count": int(scene_count),
        "merged_rows": int(len(snapshot)),
        "archive_dir": str(archive_dir),
        "snapshot_path": str(merged_path),
    }


TIMESTAMP_RE = re.compile(r"^\s*\[(\d{1,2}):(\d{2}):(\d{2})\]\s*(.*)$")


def _caption_tokens(text: str) -> list[str]:
    return [tok for tok in re.split(r"\s+", str(text or "").strip()) if tok]


def _norm_caption_token(token: str) -> str:
    return re.sub(r"[^a-z0-9']+", "", str(token or "").lower())


def _collapse_adjacent_caption_repeats(tokens: list[str]) -> list[str]:
    """Collapse exact adjacent 3+ word duplicate spans created by rolling captions."""
    out = list(tokens)
    changed = True
    while changed and len(out) >= 6:
        changed = False
        norms = [_norm_caption_token(t) for t in out]
        max_span = min(30, len(out) // 2)
        for span in range(max_span, 2, -1):
            i = 0
            while i + (2 * span) <= len(out):
                left = norms[i:i + span]
                right = norms[i + span:i + (2 * span)]
                if all(left) and left == right:
                    del out[i + span:i + (2 * span)]
                    changed = True
                    break
                i += 1
            if changed:
                break
    return out


def _dedupe_caption_points(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Remove overlap produced by YouTube rolling caption cues while preserving timestamps.

    Only exact 3+ word overlap is removed. This deliberately avoids deleting ordinary
    rhetorical repetition such as a repeated one- or two-word phrase.
    """
    cleaned: list[dict[str, Any]] = []
    history_tokens: list[str] = []
    history_norms: list[str] = []

    for point in points:
        tokens = _collapse_adjacent_caption_repeats(_caption_tokens(point.get("text", "")))
        norms = [_norm_caption_token(t) for t in tokens]

        # Remove the longest exact overlap between the already-emitted transcript tail
        # and the beginning of this rolling caption cue.
        max_overlap = min(80, len(history_norms), len(norms))
        overlap = 0
        for size in range(max_overlap, 2, -1):
            if history_norms[-size:] == norms[:size] and all(norms[:size]):
                overlap = size
                break
        if overlap:
            tokens = tokens[overlap:]
            norms = norms[overlap:]

        text = " ".join(tokens).strip()
        if not text:
            continue

        item = dict(point)
        item["text"] = text
        cleaned.append(item)
        history_tokens.extend(tokens)
        history_norms.extend(norms)
        if len(history_tokens) > 240:
            history_tokens = history_tokens[-240:]
            history_norms = history_norms[-240:]

    return cleaned


def repair_reconstructed_transcript_overlaps(db_path: Path, *, force: bool = False) -> dict[str, int]:
    """One-time local cleanup for already-saved transcript_reconstructed rows.

    No YouTube API request is made. Existing timestamps are preserved, affected mapping
    cache rows are invalidated, and future learning is rebuilt from the cleaned text.
    """
    init_db(db_path)
    meta_key = "transcript_overlap_cleanup_version"
    with _db_connect(db_path) as con:
        row = con.execute("SELECT value FROM meta WHERE key=?", (meta_key,)).fetchone()
        if not force and row and int(row["value"] or 0) >= TRANSCRIPT_OVERLAP_CLEANUP_VERSION:
            return {"videos": 0, "segments": 0}
        aids = [r["analytics_id"] for r in con.execute(
            "SELECT DISTINCT analytics_id FROM scene_snapshots WHERE source='transcript_reconstructed'"
        ).fetchall()]

    changed_videos = 0
    changed_segments = 0
    for analytics_id in aids:
        with _db_connect(db_path) as con:
            rows = con.execute(
                """
                SELECT scene_id, start_sec, end_sec, duration_sec, script_text, ordinal
                FROM scene_snapshots
                WHERE analytics_id=? AND source='transcript_reconstructed'
                ORDER BY COALESCE(ordinal, 999999), start_sec, scene_id
                """,
                (analytics_id,),
            ).fetchall()
        points = [
            {"scene_id": r["scene_id"], "start_sec": r["start_sec"], "end_sec": r["end_sec"],
             "duration_sec": r["duration_sec"], "text": r["script_text"] or "", "ordinal": r["ordinal"]}
            for r in rows
        ]
        cleaned = _dedupe_caption_points(points)
        clean_by_scene = {p["scene_id"]: p["text"] for p in cleaned}
        updates = []
        for r in rows:
            old = str(r["script_text"] or "").strip()
            new = clean_by_scene.get(r["scene_id"], "")
            if old != new:
                updates.append((new, analytics_id, r["scene_id"]))
        if updates:
            with _db_connect(db_path) as con:
                con.executemany(
                    "UPDATE scene_snapshots SET script_text=? WHERE analytics_id=? AND scene_id=? AND source='transcript_reconstructed'",
                    updates,
                )
            # Keep the permanent human-readable transcript asset synchronized with
            # the cleaned SQLite snapshot. This is local-only and makes no API call.
            asset_path = Path(db_path).parent / "youtube_assets" / str(analytics_id) / "timestamped_transcript.txt"
            if asset_path.parent.exists():
                clean_by_scene = {p["scene_id"]: p["text"] for p in cleaned}
                lines = []
                for r in rows:
                    body = clean_by_scene.get(r["scene_id"], "").strip()
                    if not body:
                        continue
                    start = int(float(r["start_sec"] or 0))
                    h = start // 3600
                    mnt = (start % 3600) // 60
                    sec = start % 60
                    lines.append(f"[{h:02d}:{mnt:02d}:{sec:02d}] {body}")
                try:
                    asset_path.write_text("\n".join(lines), encoding="utf-8")
                except OSError:
                    pass
            _invalidate_retention_mapping_cache(db_path, analytics_id)
            changed_videos += 1
            changed_segments += len(updates)

    with _db_connect(db_path) as con:
        con.execute(
            "INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (meta_key, str(TRANSCRIPT_OVERLAP_CLEANUP_VERSION)),
        )
    return {"videos": changed_videos, "segments": changed_segments}


def parse_timestamped_transcript(text: str) -> list[dict[str, Any]]:
    """
    Supports the user's format:
      [00:00:00] attention. 94% ...
      [00:00:03] 65 are making ...
    Each timestamp starts a new transcript-analysis segment.
    """
    points: list[dict[str, Any]] = []
    for raw in str(text or "").splitlines():
        m = TIMESTAMP_RE.match(raw)
        if not m:
            # Continuation lines are appended to the prior point.
            if points and raw.strip():
                points[-1]["text"] = (points[-1]["text"] + " " + raw.strip()).strip()
            continue
        h, mnt, sec, body = m.groups()
        t = int(h) * 3600 + int(mnt) * 60 + int(sec)
        points.append({"start_sec": float(t), "text": body.strip()})

    if not points:
        raise AnalyticsDBError(
            "No [HH:MM:SS] timestamps were found. Upload the timestamped transcript format."
        )

    points = _dedupe_caption_points(points)
    if not points:
        raise AnalyticsDBError("Timestamped transcript contained no unique spoken text after overlap cleanup.")

    for i, item in enumerate(points):
        next_start = points[i + 1]["start_sec"] if i + 1 < len(points) else item["start_sec"] + 3.0
        item["end_sec"] = max(item["start_sec"] + 0.01, next_start)
        item["duration_sec"] = item["end_sec"] - item["start_sec"]
        item["scene_id"] = f"TS{i+1:04d}"
    return points


def snapshot_timestamped_transcript(
    db_path: Path,
    analytics_id: str,
    text: str,
) -> int:
    points = parse_timestamped_transcript(text)
    rows = [
        (
            analytics_id, p["scene_id"], p["start_sec"], p["end_sec"], p["duration_sec"],
            p["text"], None, None, None, None, "transcript_timestamp", "transcript_reconstructed", i + 1
        )
        for i, p in enumerate(points)
    ]
    with _db_connect(db_path) as con:
        con.execute("DELETE FROM scene_snapshots WHERE analytics_id=? AND source='transcript_reconstructed'", (analytics_id,))
        con.executemany(
            """
            INSERT INTO scene_snapshots(
                analytics_id, scene_id, start_sec, end_sec, duration_sec, script_text,
                visual_mode, asset_type, overlay_type, avatar_chunk, timing_source, source, ordinal
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            rows,
        )
        con.execute(
            """
            UPDATE videos SET timeline_status='ready', timeline_source='transcript_reconstructed',
            updated_at=? WHERE analytics_id=?
            """,
            (_now(), analytics_id),
        )
    _invalidate_retention_mapping_cache(db_path, analytics_id)
    return len(rows)


def _num(value: Any, *, percent: bool = False) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip().replace(",", "")
    if not s:
        return None
    if percent:
        s = s.replace("%", "").strip()
    try:
        return float(s)
    except Exception:
        return None


def _duration_seconds(value: Any) -> float | None:
    return _parse_time(value)


def _canonical_row(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {}
    # Prefer aggregate row if YouTube labels it Total; never use "Total" as title.
    for _, row in df.iterrows():
        d = row.to_dict()
        content = str(_col(d, ["Content", "Video", "Title"]) or "").strip()
        if content.casefold() in {"total", "totals", "overall"}:
            return d
    return df.iloc[0].to_dict()


def classify_youtube_csv(df: pd.DataFrame) -> str:
    cols = {re.sub(r"[^a-z0-9]+", "", str(c).lower()) for c in df.columns}
    if any(x in cols for x in {"trafficsource", "trafficsourcetype"}):
        if any(x in cols for x in {"date", "day"}):
            return "traffic_daily"
        return "traffic_source"
    if any(x in cols for x in {"date", "day"}) and any(x in cols for x in {"engagedviews", "views", "watchtimehours"}):
        return "daily_total"
    if any(x in cols for x in {"averagepercentageviewed", "impressionsclickthroughrate", "averageviewduration"}):
        return "performance"
    return "unknown"


def import_youtube_csv(
    db_path: Path,
    analytics_id: str,
    df: pd.DataFrame,
    *,
    source_file: str = "",
) -> dict[str, Any]:
    init_db(db_path)
    kind = classify_youtube_csv(df)
    imported_at = _now()

    if kind == "performance":
        row = _canonical_row(df)
        payload = {
            "views": _num(_col(row, ["Views"])),
            "engaged_views": _num(_col(row, ["Engaged views"])),
            "watch_time_hours": _num(_col(row, ["Watch time (hours)", "Watch time"])),
            "average_view_duration_seconds": _duration_seconds(_col(row, ["Average view duration"])),
            "average_percentage_viewed": _num(_col(row, ["Average percentage viewed (%)", "Average percentage viewed"]), percent=True),
            "impressions": _num(_col(row, ["Thumbnail impressions", "Impressions"])),
            "ctr_percent": _num(_col(row, ["Thumbnail click-through rate (%)", "Thumbnail click-through rate", "Impressions click-through rate (%)", "Impressions click-through rate", "CTR"]), percent=True),
            "subscribers": _num(_col(row, ["Subscribers"])),
            "average_views_per_viewer": _num(_col(row, ["Average views per viewer"])),
            "unique_viewers": _num(_col(row, ["Unique viewers"])),
            "unique_reach": _num(_col(row, ["Unique reach"])),
            "new_viewers": _num(_col(row, ["New viewers"])),
            "returning_viewers": _num(_col(row, ["Returning viewers"])),
            "casual_viewers": _num(_col(row, ["Casual viewers"])),
            "regular_viewers": _num(_col(row, ["Regular viewers"])),
            "stayed_to_watch_percent": _num(_col(row, ["Stayed to watch (%)", "Stayed to watch"]), percent=True),
        }
        with _db_connect(db_path) as con:
            con.execute(
                """
                INSERT INTO performance_snapshots(
                    analytics_id, imported_at, report_kind, source_file,
                    views, engaged_views, watch_time_hours, average_view_duration_seconds,
                    average_percentage_viewed, impressions, ctr_percent, subscribers,
                    average_views_per_viewer, unique_viewers, unique_reach, new_viewers,
                    returning_viewers, casual_viewers, regular_viewers, stayed_to_watch_percent,
                    raw_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    analytics_id, imported_at, "performance", source_file,
                    payload["views"], payload["engaged_views"], payload["watch_time_hours"],
                    payload["average_view_duration_seconds"], payload["average_percentage_viewed"],
                    payload["impressions"], payload["ctr_percent"], payload["subscribers"],
                    payload["average_views_per_viewer"], payload["unique_viewers"], payload["unique_reach"],
                    payload["new_viewers"], payload["returning_viewers"], payload["casual_viewers"],
                    payload["regular_viewers"], payload["stayed_to_watch_percent"],
                    json.dumps(row, default=str),
                ),
            )
            con.execute(
                "UPDATE videos SET analytics_status='partial', updated_at=? WHERE analytics_id=?",
                (imported_at, analytics_id),
            )
        return {"kind": kind, "rows": 1, **payload}

    if kind == "traffic_source":
        rows = []
        for _, r in df.iterrows():
            d = r.to_dict()
            source = str(_col(d, ["Traffic source", "Traffic source type"]) or "").strip()
            if not source or source.casefold() in {"total", "totals"}:
                continue
            rows.append((
                analytics_id, imported_at, source_file, source,
                _num(_col(d, ["Views"])),
                _num(_col(d, ["Engaged views"])),
                _num(_col(d, ["Watch time (hours)", "Watch time"])),
                _duration_seconds(_col(d, ["Average view duration"])),
                _num(_col(d, ["Average percentage viewed (%)", "Average percentage viewed"]), percent=True),
                _num(_col(d, ["Impressions"])),
                _num(_col(d, ["Impressions click-through rate (%)", "Impressions click-through rate", "CTR"]), percent=True),
                json.dumps(d, default=str),
            ))
        with _db_connect(db_path) as con:
            con.executemany(
                """
                INSERT INTO traffic_source_snapshots(
                    analytics_id, imported_at, source_file, traffic_source, views, engaged_views,
                    watch_time_hours, average_view_duration_seconds, average_percentage_viewed,
                    impressions, ctr_percent, raw_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                rows,
            )
            con.execute("UPDATE videos SET analytics_status='partial', updated_at=? WHERE analytics_id=?", (imported_at, analytics_id))
        return {"kind": kind, "rows": len(rows)}

    if kind in {"traffic_daily", "daily_total"}:
        rows = []
        for _, r in df.iterrows():
            d = r.to_dict()
            rows.append((
                analytics_id, imported_at, kind, source_file,
                str(_col(d, ["Date", "Day"]) or "").strip() or None,
                str(_col(d, ["Traffic source", "Traffic source type"]) or "").strip() or None,
                _num(_col(d, ["Engaged views"])),
                _num(_col(d, ["Views"])),
                _num(_col(d, ["Watch time (hours)", "Watch time"])),
                json.dumps(d, default=str),
            ))
        with _db_connect(db_path) as con:
            con.executemany(
                """
                INSERT INTO daily_series(
                    analytics_id, imported_at, series_type, source_file, date, traffic_source,
                    engaged_views, views, watch_time_hours, raw_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                rows,
            )
            con.execute("UPDATE videos SET analytics_status='partial', updated_at=? WHERE analytics_id=?", (imported_at, analytics_id))
        return {"kind": kind, "rows": len(rows)}

    raise AnalyticsDBError("CSV format was not recognized as Performance, Traffic Source, or Daily Analytics data.")



def processed_reporting_report_ids(db_path: Path, job_id: str) -> set[str]:
    init_db(db_path)
    with _db_connect(db_path) as con:
        rows = con.execute(
            "SELECT report_id FROM reporting_reports WHERE job_id=?",
            (str(job_id),),
        ).fetchall()
    return {str(r["report_id"]) for r in rows}


def import_reach_report(
    db_path: Path,
    *,
    job_id: str,
    report_type_id: str,
    report_meta: dict[str, Any],
    df: pd.DataFrame,
    source_file: str = "youtube_reporting_api",
) -> dict[str, Any]:
    """Persist one YouTube Reporting API reach report.

    Reach reports are daily. If YouTube later publishes a backfill for the same
    video/date, keep the row from the newer report createTime.
    """
    init_db(db_path)
    report_id = str(report_meta.get("id") or "").strip()
    if not report_id:
        raise AnalyticsDBError("Reach report is missing report id.")
    create_time = str(report_meta.get("createTime") or "")
    start_time = str(report_meta.get("startTime") or "")
    end_time = str(report_meta.get("endTime") or "")
    imported_at = _now()

    cols = {str(c).strip().lower(): c for c in df.columns}
    video_col = cols.get("video_id")
    date_col = cols.get("date") or cols.get("day")
    imp_col = cols.get("video_thumbnail_impressions")
    ctr_col = cols.get("video_thumbnail_impressions_ctr")
    if not video_col or not imp_col or not ctr_col:
        raise AnalyticsDBError(
            "Reach report must contain video_id, video_thumbnail_impressions, "
            "and video_thumbnail_impressions_ctr."
        )

    rows_to_write: list[tuple[Any, ...]] = []
    unknown_video_ids = 0
    with _db_connect(db_path) as con:
        video_map = {
            str(r["youtube_video_id"]): str(r["analytics_id"])
            for r in con.execute(
                "SELECT analytics_id,youtube_video_id FROM videos "
                "WHERE youtube_video_id IS NOT NULL AND youtube_video_id<>''"
            ).fetchall()
        }

        ctr_values = pd.to_numeric(df[ctr_col], errors="coerce")
        # Reporting API percentage fields can be represented as fractions.
        # Normalize a fractional column (0..1) into the app's 0..100 convention.
        fractional_ctr = bool(ctr_values.notna().any() and ctr_values.dropna().abs().max() <= 1.0)

        for _, row in df.iterrows():
            video_id = str(row.get(video_col) or "").strip()
            aid = video_map.get(video_id)
            if not aid:
                unknown_video_ids += 1
                continue
            report_date = str(row.get(date_col) or "")[:10] if date_col else start_time[:10]
            if not report_date:
                continue
            impressions = _num(row.get(imp_col))
            ctr = _num(row.get(ctr_col), percent=True)
            if ctr is not None and fractional_ctr:
                ctr *= 100.0
            rows_to_write.append(
                (
                    aid, report_date, impressions, ctr, report_id, create_time,
                    source_file, imported_at,
                )
            )

        written = 0
        for payload in rows_to_write:
            existing = con.execute(
                "SELECT report_create_time FROM reach_daily WHERE analytics_id=? AND report_date=?",
                (payload[0], payload[1]),
            ).fetchone()
            if existing and str(existing["report_create_time"] or "") > create_time:
                continue
            con.execute(
                """
                INSERT INTO reach_daily(
                    analytics_id,report_date,impressions,ctr_percent,report_id,
                    report_create_time,source_file,imported_at
                ) VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(analytics_id,report_date) DO UPDATE SET
                    impressions=excluded.impressions,
                    ctr_percent=excluded.ctr_percent,
                    report_id=excluded.report_id,
                    report_create_time=excluded.report_create_time,
                    source_file=excluded.source_file,
                    imported_at=excluded.imported_at
                """,
                payload,
            )
            written += 1

        con.execute(
            """
            INSERT OR REPLACE INTO reporting_reports(
                job_id,report_id,report_type_id,start_time,end_time,create_time,processed_at
            ) VALUES(?,?,?,?,?,?,?)
            """,
            (
                str(job_id), report_id, str(report_type_id), start_time,
                end_time, create_time, imported_at,
            ),
        )
    return {
        "report_id": report_id,
        "rows_written": written,
        "unknown_video_ids": unknown_video_ids,
    }


def reach_summary_by_video(db_path: Path) -> pd.DataFrame:
    """Return weighted thumbnail CTR + impressions from permanently stored reach days."""
    init_db(db_path)
    with _db_connect(db_path) as con:
        rows = con.execute(
            """
            SELECT
                analytics_id,
                SUM(COALESCE(impressions,0)) AS reach_impressions,
                CASE
                    WHEN SUM(COALESCE(impressions,0)) > 0 THEN
                        SUM(COALESCE(impressions,0) * COALESCE(ctr_percent,0))
                        / SUM(COALESCE(impressions,0))
                    ELSE NULL
                END AS reach_ctr_percent,
                MIN(report_date) AS reach_start_date,
                MAX(report_date) AS reach_end_date,
                COUNT(*) AS reach_days
            FROM reach_daily
            GROUP BY analytics_id
            """
        ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def list_videos(db_path: Path) -> list[dict[str, Any]]:
    init_db(db_path)
    with _db_connect(db_path) as con:
        rows = con.execute(
            """
            SELECT *,
                COALESCE(NULLIF(youtube_title,''), NULLIF(locked_title,''), project_slug, analytics_id) AS display_title
            FROM videos
            ORDER BY created_at DESC, updated_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_video(db_path: Path, analytics_id: str) -> dict[str, Any] | None:
    with _db_connect(db_path) as con:
        row = con.execute("SELECT * FROM videos WHERE analytics_id=?", (analytics_id,)).fetchone()
        return dict(row) if row else None


def latest_performance(db_path: Path, analytics_id: str) -> dict[str, Any] | None:
    with _db_connect(db_path) as con:
        row = con.execute(
            "SELECT * FROM performance_snapshots WHERE analytics_id=? ORDER BY id DESC LIMIT 1",
            (analytics_id,),
        ).fetchone()
        return dict(row) if row else None


def record_thumbnail_snapshot(
    db_path: Path, analytics_id: str, *, youtube_video_id: str, downloaded_at: str,
    source_url: str, source_variant: str, file_path: str, width: int, height: int, sha256: str,
) -> int:
    """Record a permanent current-thumbnail snapshot without storing image bytes in SQLite."""
    init_db(db_path)
    with _db_connect(db_path) as con:
        video = con.execute("SELECT youtube_video_id FROM videos WHERE analytics_id=?", (analytics_id,)).fetchone()
        if not video:
            raise AnalyticsDBError(f"Unknown analytics_id: {analytics_id}")
        bound = str(video["youtube_video_id"] or "").strip()
        if bound != str(youtube_video_id or "").strip():
            raise AnalyticsDBError("Thumbnail Video ID does not match the permanent youtube_video_id binding.")
        con.execute("UPDATE thumbnail_snapshots SET is_current=0 WHERE analytics_id=?", (analytics_id,))
        cur = con.execute(
            """INSERT INTO thumbnail_snapshots
               (analytics_id,youtube_video_id,downloaded_at,source_url,source_variant,file_path,width,height,sha256,is_current,analysis_status)
               VALUES (?,?,?,?,?,?,?,?,?,1,'pending')""",
            (analytics_id, youtube_video_id, downloaded_at, source_url, source_variant, file_path, int(width), int(height), sha256),
        )
        con.commit()
        return int(cur.lastrowid)


def latest_thumbnail_snapshot(db_path: Path, analytics_id: str) -> dict[str, Any] | None:
    init_db(db_path)
    with _db_connect(db_path) as con:
        row = con.execute(
            "SELECT * FROM thumbnail_snapshots WHERE analytics_id=? AND is_current=1 ORDER BY id DESC LIMIT 1",
            (analytics_id,),
        ).fetchone()
        return dict(row) if row else None


def thumbnail_inventory_df(db_path: Path) -> pd.DataFrame:
    init_db(db_path)
    with _db_connect(db_path) as con:
        rows = con.execute(
            """SELECT v.analytics_id,v.youtube_video_id,
                      COALESCE(NULLIF(v.youtube_title,''),NULLIF(v.locked_title,''),v.project_slug,v.analytics_id) AS title,
                      t.downloaded_at,t.source_variant,t.file_path,t.width,t.height,t.sha256,t.analysis_status
               FROM videos v
               LEFT JOIN thumbnail_snapshots t ON t.analytics_id=v.analytics_id AND t.is_current=1
               WHERE v.youtube_video_id IS NOT NULL AND v.youtube_video_id<>''
               ORDER BY v.created_at DESC"""
        ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def scene_snapshot_df(db_path: Path, analytics_id: str) -> pd.DataFrame:
    with _db_connect(db_path) as con:
        rows = con.execute(
            """
            SELECT scene_id,start_sec,end_sec,duration_sec,script_text,visual_mode,asset_type,
                   overlay_type,avatar_chunk,timing_source,source,ordinal
            FROM scene_snapshots WHERE analytics_id=? ORDER BY ordinal
            """,
            (analytics_id,),
        ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def traffic_source_df(db_path: Path, analytics_id: str) -> pd.DataFrame:
    with _db_connect(db_path) as con:
        rows = con.execute(
            """
            SELECT traffic_source,views,engaged_views,watch_time_hours,average_view_duration_seconds,
                   average_percentage_viewed,impressions,ctr_percent,imported_at,source_file
            FROM traffic_source_snapshots WHERE analytics_id=? ORDER BY id
            """,
            (analytics_id,),
        ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def mark_missing_project_folders(db_path: Path) -> int:
    """Never delete analytics. Only mark local project folders unavailable."""
    init_db(db_path)
    changed = 0
    with _db_connect(db_path) as con:
        rows = con.execute(
            "SELECT analytics_id, project_path_at_creation FROM videos WHERE source_type='project'"
        ).fetchall()
        for row in rows:
            p = str(row["project_path_at_creation"] or "").strip()
            status = "available" if p and Path(p).exists() else "deleted"
            cur = con.execute(
                "UPDATE videos SET project_folder_status=?, updated_at=? WHERE analytics_id=? AND project_folder_status<>?",
                (status, _now(), row["analytics_id"], status),
            )
            changed += cur.rowcount
    return changed


def _find_video_id_column(df: pd.DataFrame) -> str | None:
    aliases = [
        "Video ID", "video_id", "Video id", "Content ID", "content_id",
        "YouTube Video ID", "youtube_video_id"
    ]
    norm_map = {
        re.sub(r"[^a-z0-9]+", "", str(c).lower()): c
        for c in df.columns
    }
    for alias in aliases:
        key = re.sub(r"[^a-z0-9]+", "", alias.lower())
        if key in norm_map:
            return norm_map[key]

    # YouTube Studio channel Content exports commonly use a column literally
    # named "Content" for the 11-character YouTube video ID. Only accept it
    # as identity when the non-total values actually look like YouTube IDs.
    content_col = norm_map.get("content")
    if content_col is not None:
        vals = [str(v).strip() for v in df[content_col].dropna().tolist()]
        vals = [v for v in vals if v and v.casefold() not in {"total","totals","overall","all"}]
        if vals:
            sample = vals[:50]
            looks = sum(bool(re.fullmatch(r"[A-Za-z0-9_-]{11}", v)) for v in sample)
            if looks >= max(1, int(len(sample) * 0.8)):
                return content_col
    return None


def _find_title_column(df: pd.DataFrame) -> str | None:
    aliases = ["Video title", "Title", "Content title", "Video"]
    norm_map = {
        re.sub(r"[^a-z0-9]+", "", str(c).lower()): c
        for c in df.columns
    }
    for alias in aliases:
        key = re.sub(r"[^a-z0-9]+", "", alias.lower())
        if key in norm_map:
            return norm_map[key]

    # Some exports use Content as title, but only when Content is not acting
    # as the 11-character Video ID column.
    content_col = norm_map.get("content")
    if content_col is not None:
        vals = [str(v).strip() for v in df[content_col].dropna().tolist()]
        vals = [v for v in vals if v and v.casefold() not in {"total","totals","overall","all"}]
        if vals:
            sample = vals[:50]
            id_like = sum(bool(re.fullmatch(r"[A-Za-z0-9_-]{11}", v)) for v in sample)
            if id_like < max(1, int(len(sample) * 0.8)):
                return content_col
    return None


def _normalize_video_id(value: Any) -> str:
    return str(value or "").strip()


def _normalize_title(value: Any) -> str:
    s = str(value or "").strip()
    if s.casefold() in {"total", "totals", "overall", "all"}:
        return ""
    return s


def _title_similarity(a: Any, b: Any) -> float:
    """Conservative similarity for reconciling a changed YouTube title to a draft project."""
    left = _normalized_title(a)
    right = _normalized_title(b)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    seq = SequenceMatcher(None, left, right).ratio()
    lt = set(left.split())
    rt = set(right.split())
    union = lt | rt
    jaccard = (len(lt & rt) / len(union)) if union else 0.0
    # Token overlap protects against punctuation/order edits; sequence similarity
    # protects against accidentally matching titles with only generic words.
    return max(seq, (0.55 * seq) + (0.45 * jaccard))


def _candidate_timeline_duration(con: sqlite3.Connection, analytics_id: str) -> float | None:
    row = con.execute(
        """
        SELECT MAX(end_sec) AS max_end, SUM(duration_sec) AS total_duration
        FROM scene_snapshots
        WHERE analytics_id=? AND source='actual_timeline'
        """,
        (analytics_id,),
    ).fetchone()
    if not row:
        return None
    max_end = row["max_end"]
    total = row["total_duration"]
    value = max_end if max_end is not None else total
    try:
        return float(value) if value is not None and float(value) > 0 else None
    except Exception:
        return None


def _duration_similarity(imported_duration: float | None, candidate_duration: float | None) -> float | None:
    if not imported_duration or not candidate_duration or imported_duration <= 0 or candidate_duration <= 0:
        return None
    diff = abs(float(imported_duration) - float(candidate_duration))
    base = max(float(imported_duration), float(candidate_duration))
    return max(0.0, 1.0 - (diff / base))


def _date_compatibility(publish_date: str | None, created_at: str | None) -> float | None:
    if not publish_date or not created_at:
        return None
    try:
        pub = datetime.fromisoformat(str(publish_date)[:10]).date()
        created = datetime.fromisoformat(str(created_at).replace("Z", "+00:00")).date()
    except Exception:
        return None
    days = (pub - created).days
    if days < -1:
        return 0.0
    if days <= 90:
        return 1.0
    if days <= 180:
        return 0.75
    if days <= 365:
        return 0.4
    return 0.2


def _find_unlinked_project_match(
    con: sqlite3.Connection,
    *,
    title: str,
    duration_sec: float | None = None,
    publish_date: str | None = None,
) -> str | None:
    """Return one high-confidence unlinked project match, otherwise None.

    The matcher deliberately refuses ambiguous candidates. Exact normalized titles
    still win immediately. Changed-title reconciliation requires strong title
    similarity, or good title similarity plus a near-matching production duration.
    """
    if not title:
        return None
    rows = con.execute(
        """
        SELECT analytics_id, locked_title, project_slug, created_at
        FROM videos
        WHERE project_id IS NOT NULL
          AND (youtube_video_id IS NULL OR youtube_video_id='')
        """
    ).fetchall()
    if not rows:
        return None

    normalized = _normalized_title(title)
    exact = [r for r in rows if normalized and normalized == _normalized_title(r["locked_title"] or r["project_slug"])]
    if len(exact) == 1:
        return exact[0]["analytics_id"]
    if len(exact) > 1:
        return None

    scored: list[tuple[float, float, float | None, str]] = []
    for r in rows:
        candidate_title = r["locked_title"] or r["project_slug"] or ""
        title_score = _title_similarity(title, candidate_title)
        candidate_duration = _candidate_timeline_duration(con, r["analytics_id"])
        duration_score = _duration_similarity(duration_sec, candidate_duration)
        date_score = _date_compatibility(publish_date, r["created_at"])

        weighted = title_score
        weight = 0.75
        total = title_score * weight
        if duration_score is not None:
            total += duration_score * 0.20
            weight += 0.20
        if date_score is not None:
            total += date_score * 0.05
            weight += 0.05
        weighted = total / weight if weight else title_score
        scored.append((weighted, title_score, duration_score, r["analytics_id"]))

    scored.sort(reverse=True, key=lambda x: x[0])
    best = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0
    margin = best[0] - second_score
    high_title_confidence = best[1] >= 0.86 and margin >= 0.08
    title_plus_duration_confidence = (
        best[1] >= 0.55
        and best[2] is not None
        and best[2] >= 0.95
        and margin >= 0.10
    )
    if high_title_confidence or title_plus_duration_confidence:
        return best[3]
    return None


def _get_or_create_video_by_identity(
    db_path: Path,
    *,
    video_id: str | None,
    title: str | None,
    duration_sec: float | None = None,
    publish_date: str | None = None,
) -> str:
    """Resolve YouTube imports by permanent Video ID only.

    Never guess a local project from title/duration/date. If the Video ID has not
    been manually bound yet, keep the API data in a YouTube-only staging record.
    """
    init_db(db_path)
    vid = _normalize_video_id(video_id)
    title = _normalize_title(title)
    with _db_connect(db_path) as con:
        if vid:
            row = con.execute("SELECT analytics_id FROM videos WHERE youtube_video_id=?", (vid,)).fetchone()
            if row:
                if title:
                    con.execute(
                        "UPDATE videos SET youtube_title=?, publish_date=COALESCE(NULLIF(?,''), publish_date), updated_at=? WHERE analytics_id=?",
                        (title, publish_date or "", _now(), row["analytics_id"]),
                    )
                return row["analytics_id"]
    return register_youtube_only_video(
        db_path,
        title=title or (vid and f"YouTube Video {vid}") or "Untitled YouTube Video",
        youtube_video_id=vid or None,
        publish_date=publish_date or None,
    )

def link_youtube_record_to_project(
    db_path: Path,
    project_analytics_id: str,
    youtube_analytics_id: str,
) -> str:
    """One-time manual fallback: merge a YouTube-only row into an existing project row.

    The project's analytics_id remains permanent, so its archived script/timeline
    stays attached. Imported YouTube snapshots are moved onto that same record.
    """
    init_db(db_path)
    project_analytics_id = str(project_analytics_id or "").strip()
    youtube_analytics_id = str(youtube_analytics_id or "").strip()
    if not project_analytics_id or not youtube_analytics_id or project_analytics_id == youtube_analytics_id:
        raise AnalyticsDBError("Choose one project record and one separate YouTube-only record.")

    with _db_connect(db_path) as con:
        project = con.execute("SELECT * FROM videos WHERE analytics_id=?", (project_analytics_id,)).fetchone()
        youtube = con.execute("SELECT * FROM videos WHERE analytics_id=?", (youtube_analytics_id,)).fetchone()
        if not project or not youtube:
            raise AnalyticsDBError("Selected analytics record no longer exists.")
        if not project["project_id"]:
            raise AnalyticsDBError("Target record is not linked to a local project.")
        if project["youtube_video_id"]:
            raise AnalyticsDBError("Target project already has a YouTube Video ID.")
        if youtube["source_type"] != "youtube_only" or not youtube["youtube_video_id"]:
            raise AnalyticsDBError("Source must be an unlinked YouTube-only record with a Video ID.")

        # Move append-only analytics tables.
        for table in ("performance_snapshots", "traffic_source_snapshots", "daily_series", "retention_points", "comments"):
            con.execute(f"UPDATE {table} SET analytics_id=? WHERE analytics_id=?", (project_analytics_id, youtube_analytics_id))

        # Scene rows can share keys; preserve the project's original actual timeline
        # and add only non-conflicting transcript/scene rows from the YouTube record.
        con.execute(
            """
            INSERT OR IGNORE INTO scene_snapshots(
                analytics_id, scene_id, start_sec, end_sec, duration_sec, script_text,
                visual_mode, asset_type, overlay_type, avatar_chunk, timing_source, source, ordinal
            )
            SELECT ?, scene_id, start_sec, end_sec, duration_sec, script_text,
                   visual_mode, asset_type, overlay_type, avatar_chunk, timing_source, source, ordinal
            FROM scene_snapshots WHERE analytics_id=?
            """,
            (project_analytics_id, youtube_analytics_id),
        )
        con.execute("DELETE FROM scene_snapshots WHERE analytics_id=?", (youtube_analytics_id,))

        # Release the unique YouTube Video ID from the temporary YouTube-only row
        # after all of its child analytics have been moved.
        con.execute("DELETE FROM videos WHERE analytics_id=?", (youtube_analytics_id,))
        con.execute(
            """
            UPDATE videos
            SET youtube_title=COALESCE(NULLIF(?,''), youtube_title),
                youtube_video_id=?,
                publish_date=COALESCE(NULLIF(?,''), publish_date),
                publish_weekday=COALESCE(NULLIF(?,''), publish_weekday),
                source_type='project_linked',
                analytics_status=CASE WHEN ?<>'pending' THEN ? ELSE analytics_status END,
                retention_status=CASE WHEN ?<>'pending' THEN ? ELSE retention_status END,
                comments_status=CASE WHEN ?<>'pending' THEN ? ELSE comments_status END,
                updated_at=?
            WHERE analytics_id=?
            """,
            (
                youtube["youtube_title"] or "", youtube["youtube_video_id"],
                youtube["publish_date"] or "", youtube["publish_weekday"] or "",
                youtube["analytics_status"], youtube["analytics_status"],
                youtube["retention_status"], youtube["retention_status"],
                youtube["comments_status"], youtube["comments_status"],
                _now(), project_analytics_id,
            ),
        )
    return project_analytics_id



def bind_youtube_video_id_to_project(db_path: Path, project_analytics_id: str, youtube_video_id: str) -> str:
    """Explicitly bind a YouTube Video ID to one existing local project.

    If API sync already created a YouTube-only staging row for this Video ID, its
    analytics are merged into the selected project's permanent analytics_id.
    """
    init_db(db_path)
    aid = str(project_analytics_id or "").strip()
    vid = _normalize_video_id(youtube_video_id)
    if not aid:
        raise AnalyticsDBError("Select a project first.")
    if not vid:
        raise AnalyticsDBError("Enter a valid YouTube Video ID.")
    with _db_connect(db_path) as con:
        project = con.execute("SELECT * FROM videos WHERE analytics_id=?", (aid,)).fetchone()
        if not project or not project["project_id"]:
            raise AnalyticsDBError("Selected record is not a local project.")
        current = str(project["youtube_video_id"] or "").strip()
        if current:
            if current == vid:
                return aid
            raise AnalyticsDBError(f"This project is already linked to YouTube Video ID {current}. Unlink/relink is not performed automatically.")
        owner = con.execute("SELECT analytics_id, source_type, project_id FROM videos WHERE youtube_video_id=?", (vid,)).fetchone()
    if owner:
        if owner["analytics_id"] == aid:
            return aid
        if owner["source_type"] == "youtube_only" and not owner["project_id"]:
            return link_youtube_record_to_project(db_path, aid, owner["analytics_id"])
        raise AnalyticsDBError("That YouTube Video ID is already linked to another project/analytics record.")
    with _db_connect(db_path) as con:
        con.execute(
            "UPDATE videos SET youtube_video_id=?, source_type='project_linked', updated_at=? WHERE analytics_id=?",
            (vid, _now(), aid),
        )
    return aid

def bulk_import_channel_content_csv(
    db_path: Path,
    df: pd.DataFrame,
    *,
    source_file: str = "",
    snapshot_label: str = "",
) -> dict[str, Any]:
    """
    Import a channel-wide YouTube Studio Content/Performance CSV containing many videos.
    Video ID is the preferred identity. Draft projects are reconciled conservatively
    by title similarity plus available duration/date evidence; exact normalized title
    remains a direct match. Ambiguous rows stay YouTube-only for one-time manual attach.
    One latest performance snapshot is appended per video per import run.
    """
    init_db(db_path)
    if df.empty:
        raise AnalyticsDBError("Content CSV has no rows.")

    video_id_col = _find_video_id_column(df)
    title_col = _find_title_column(df)
    if video_id_col is None and title_col is None:
        raise AnalyticsDBError(
            "Channel-wide Content CSV must contain a Video ID or Video title/Content column."
        )

    imported = 0
    created_or_linked = 0
    skipped = 0
    errors: list[str] = []

    for idx, row in df.iterrows():
        d = row.to_dict()
        video_id = _normalize_video_id(d.get(video_id_col)) if video_id_col else ""
        title = _normalize_title(d.get(title_col)) if title_col else ""
        publish_value = _col(d, ["Video publish time", "Publish time", "Published at", "Publish date", "Video publish date"])
        publish_date = _parse_publish_date(publish_value)
        publish_weekday = _weekday_from_iso_date(publish_date)

        # Skip aggregate/summary rows such as YouTube Studio's "Total" row.
        if (video_id and video_id.strip().lower() in {"total", "totals"}) or (title and title.strip().lower() in {"total", "totals"}):
            skipped += 1
            continue
        if not video_id and not title:
            skipped += 1
            continue

        try:
            video_duration = _duration_seconds(_col(d, ["Duration", "Video duration", "duration_sec"]))
            aid = _get_or_create_video_by_identity(
                db_path,
                video_id=video_id or None,
                title=title or None,
                duration_sec=video_duration,
                publish_date=publish_date or None,
            )
            created_or_linked += 1

            # Import this one row using the existing performance importer.
            one = pd.DataFrame([d])
            result = import_youtube_csv(
                db_path,
                aid,
                one,
                source_file=source_file,
            )
            if result.get("kind") != "performance":
                raise AnalyticsDBError("Row was not recognized as performance data.")
            imported += 1

            # Update title/video id if present.
            update_video_identity(
                db_path,
                aid,
                youtube_title=title or None,
                youtube_video_id=video_id or None,
                publish_date=publish_date or None,
                publish_weekday=publish_weekday or None,
            )

            if snapshot_label:
                with _db_connect(db_path) as con:
                    con.execute(
                        """
                        UPDATE performance_snapshots
                        SET date_range_label=?
                        WHERE id=(
                            SELECT id FROM performance_snapshots
                            WHERE analytics_id=?
                            ORDER BY id DESC LIMIT 1
                        )
                        """,
                        (snapshot_label, aid),
                    )

        except Exception as exc:
            errors.append(f"Row {idx+2}: {exc}")

    return {
        "kind": "channel_content_bulk",
        "imported_videos": imported,
        "linked_or_created_records": created_or_linked,
        "skipped_rows": skipped,
        "errors": errors,
        "video_id_column": video_id_col,
        "title_column": title_col,
    }


def bulk_import_channel_traffic_csv(
    db_path: Path,
    df: pd.DataFrame,
    *,
    source_file: str = "",
) -> dict[str, Any]:
    """
    Import channel-wide Traffic Source data for multiple videos.

    Requires a video identity column (preferably Video ID) plus Traffic source.
    Rows are grouped by video and passed to the existing traffic-source importer.
    """
    init_db(db_path)
    if df.empty:
        raise AnalyticsDBError("Traffic Source CSV has no rows.")

    video_id_col = _find_video_id_column(df)
    title_col = _find_title_column(df)

    traffic_col = None
    norm_map = {
        re.sub(r"[^a-z0-9]+", "", str(c).lower()): c
        for c in df.columns
    }
    for alias in ["Traffic source", "Traffic source type"]:
        k = re.sub(r"[^a-z0-9]+", "", alias.lower())
        if k in norm_map:
            traffic_col = norm_map[k]
            break

    if traffic_col is None:
        raise AnalyticsDBError("Could not find Traffic source column.")
    if video_id_col is None and title_col is None:
        raise AnalyticsDBError(
            "Channel-wide Traffic Source CSV must contain Video ID or Video title/Content."
        )

    # Build a stable grouping key from Video ID first, title second.
    working = df.copy()
    def identity_key(row):
        vid = _normalize_video_id(row.get(video_id_col)) if video_id_col else ""
        title = _normalize_title(row.get(title_col)) if title_col else ""
        if vid:
            return f"id::{vid}"
        if title:
            return f"title::{re.sub(r'[^a-z0-9]+','', title.casefold())}"
        return ""
    working["__identity_key"] = working.apply(identity_key, axis=1)
    working = working[working["__identity_key"] != ""]

    imported_videos = 0
    imported_rows = 0
    errors: list[str] = []

    for key, group in working.groupby("__identity_key", sort=False):
        first = group.iloc[0]
        video_id = _normalize_video_id(first.get(video_id_col)) if video_id_col else ""
        title = _normalize_title(first.get(title_col)) if title_col else ""
        try:
            aid = _get_or_create_video_by_identity(
                db_path,
                video_id=video_id or None,
                title=title or None,
            )
            cleaned = group.drop(columns=["__identity_key"])
            result = import_youtube_csv(
                db_path,
                aid,
                cleaned,
                source_file=source_file,
            )
            if result.get("kind") != "traffic_source":
                raise AnalyticsDBError("Grouped rows were not recognized as Traffic Source data.")
            update_video_identity(
                db_path,
                aid,
                youtube_title=title or None,
                youtube_video_id=video_id or None,
            )
            imported_videos += 1
            imported_rows += int(result.get("rows", 0))
        except Exception as exc:
            errors.append(f"{title or video_id or key}: {exc}")

    return {
        "kind": "channel_traffic_bulk",
        "imported_videos": imported_videos,
        "imported_rows": imported_rows,
        "errors": errors,
        "video_id_column": video_id_col,
        "title_column": title_col,
        "traffic_source_column": traffic_col,
    }


def has_transcript_snapshot(db_path: Path, analytics_id: str) -> bool:
    with _db_connect(db_path) as con:
        row = con.execute(
            "SELECT 1 FROM scene_snapshots WHERE analytics_id=? AND source='transcript_reconstructed' LIMIT 1",
            (analytics_id,),
        ).fetchone()
    return bool(row)


def needs_transcript_upload(db_path: Path, analytics_id: str) -> bool:
    """Ask only when neither Actual Timeline nor transcript snapshot exists."""
    with _db_connect(db_path) as con:
        row = con.execute(
            "SELECT timeline_source, timeline_status FROM videos WHERE analytics_id=?",
            (analytics_id,),
        ).fetchone()
        if not row:
            return True
        source = str(row["timeline_source"] or "").strip()
        if source in {"actual_timeline", "transcript_reconstructed"}:
            return False
        actual = con.execute(
            "SELECT 1 FROM scene_snapshots WHERE analytics_id=? AND source='actual_timeline' LIMIT 1",
            (analytics_id,),
        ).fetchone()
        if actual:
            return False
        trans = con.execute(
            "SELECT 1 FROM scene_snapshots WHERE analytics_id=? AND source='transcript_reconstructed' LIMIT 1",
            (analytics_id,),
        ).fetchone()
        return not bool(trans)


def _weekday_from_iso_date(value: str | None) -> str | None:
    if not value:
        return None
    dt = pd.to_datetime(value, errors="coerce")
    if pd.isna(dt):
        return None
    return dt.day_name()

def _parse_publish_date(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in {"none", "nan", "nat"}:
        return None
    dt = pd.to_datetime(s, errors="coerce")
    if pd.isna(dt):
        return None
    return dt.date().isoformat()


def weekday_performance_summary(db_path: Path) -> pd.DataFrame:
    dashboard = channel_dashboard_data(db_path)
    df = dashboard.get("videos")
    if df is None or df.empty:
        return pd.DataFrame()
    df = df[df["publish_date"].notna() & df["publish_date"].astype(str).str.strip().ne("")].copy()
    if df.empty:
        return pd.DataFrame()

    df["publish_dt"] = pd.to_datetime(df["publish_date"], errors="coerce")
    df = df[df["publish_dt"].notna()].copy()
    if df.empty:
        return pd.DataFrame()

    df["weekday"] = df["publish_weekday"].where(
        df["publish_weekday"].astype(str).str.strip().ne(""),
        df["publish_dt"].dt.day_name(),
    )
    df["weekday_num"] = df["publish_dt"].dt.weekday
    for c in ["views","impressions","ctr_percent","average_view_duration_seconds",
              "average_percentage_viewed","watch_time_hours","subscribers"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return (
        df.groupby(["weekday","weekday_num"], as_index=False)
          .agg(
              videos=("analytics_id","count"),
              avg_views=("views","mean"),
              avg_impressions=("impressions","mean"),
              avg_ctr=("ctr_percent","mean"),
              avg_avd_seconds=("average_view_duration_seconds","mean"),
              avg_apv=("average_percentage_viewed","mean"),
              avg_watch_hours=("watch_time_hours","mean"),
              avg_subscribers=("subscribers","mean"),
          )
          .sort_values("weekday_num")
          .reset_index(drop=True)
    )


def channel_dashboard_data(db_path: Path) -> dict[str, Any]:
    """
    Read-only channel dashboard dataset using the latest performance snapshot
    for each video. No workflow/project files are modified.
    """
    init_db(db_path)
    with _db_connect(db_path) as con:
        rows = con.execute(
            """
            SELECT
                v.analytics_id,
                COALESCE(NULLIF(v.youtube_title,''), NULLIF(v.locked_title,''), v.project_slug, v.analytics_id) AS title,
                v.youtube_video_id,
                v.publish_date,
                v.publish_weekday,
                v.source_type,
                v.project_folder_status,
                v.timeline_source,
                v.analytics_status,
                p.views,
                p.engaged_views,
                p.watch_time_hours,
                p.average_view_duration_seconds,
                p.average_percentage_viewed,
                p.impressions,
                p.ctr_percent,
                p.subscribers,
                p.average_views_per_viewer,
                p.unique_viewers,
                p.unique_reach,
                p.new_viewers,
                p.returning_viewers,
                p.imported_at
            FROM videos v
            LEFT JOIN performance_snapshots p
              ON p.id = (
                  SELECT p2.id
                  FROM performance_snapshots p2
                  WHERE p2.analytics_id = v.analytics_id
                  ORDER BY p2.id DESC
                  LIMIT 1
              )
            WHERE v.youtube_video_id IS NOT NULL AND v.youtube_video_id <> ''
            ORDER BY COALESCE(v.publish_date,'') DESC, v.created_at DESC
            """
        ).fetchall()

    df = pd.DataFrame([dict(r) for r in rows])
    if df.empty:
        return {"videos": df, "summary": {}}

    numeric_cols = [
        "views","engaged_views","watch_time_hours","average_view_duration_seconds",
        "average_percentage_viewed","impressions","ctr_percent","subscribers",
        "average_views_per_viewer","unique_viewers","unique_reach","new_viewers","returning_viewers"
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Reach/CTR comes from the YouTube Reporting API. Keep it independent from
    # the latest performance snapshot so daily Analytics API syncs cannot wipe
    # out CTR by inserting a newer snapshot with null reach fields.
    reach = reach_summary_by_video(db_path)
    if not reach.empty:
        df = df.merge(reach, on="analytics_id", how="left")
        df["impressions"] = pd.to_numeric(df.get("reach_impressions"), errors="coerce").combine_first(
            pd.to_numeric(df.get("impressions"), errors="coerce")
        )
        df["ctr_percent"] = pd.to_numeric(df.get("reach_ctr_percent"), errors="coerce").combine_first(
            pd.to_numeric(df.get("ctr_percent"), errors="coerce")
        )
    else:
        df["reach_start_date"] = None
        df["reach_end_date"] = None
        df["reach_days"] = 0

    scored = df[df["views"].notna()].copy()
    summary = {
        "registered_videos": int(len(df)),
        "videos_with_analytics": int(len(scored)),
        "total_views": float(scored["views"].sum(skipna=True)) if not scored.empty else 0.0,
        "total_watch_hours": float(scored["watch_time_hours"].sum(skipna=True)) if not scored.empty else 0.0,
        "avg_ctr": float(scored["ctr_percent"].mean(skipna=True)) if scored["ctr_percent"].notna().any() else None,
        "avg_apv": float(scored["average_percentage_viewed"].mean(skipna=True)) if scored["average_percentage_viewed"].notna().any() else None,
        "avg_avd_seconds": float(scored["average_view_duration_seconds"].mean(skipna=True)) if scored["average_view_duration_seconds"].notna().any() else None,
        "total_subscribers": float(scored["subscribers"].sum(skipna=True)) if scored["subscribers"].notna().any() else None,
    }
    return {"videos": df, "summary": summary}


def winner_loser_learning_data(db_path: Path) -> dict[str, Any]:
    """Channel-relative learning with content learning independent from CTR.

    Average % Viewed is enough to run content-hold learning. CTR is used only
    for packaging diagnosis when reach data is available from YouTube Reporting
    API (or a manual import). This prevents missing CTR from blanking the entire
    Learning Engine.
    """
    dashboard = channel_dashboard_data(db_path)
    df = dashboard.get("videos")
    if df is None or df.empty:
        return {"videos": pd.DataFrame(), "summary": {}, "recommendations": [], "patterns": pd.DataFrame()}

    work = df[df["average_percentage_viewed"].notna()].copy()
    if work.empty:
        return {"videos": work, "summary": {}, "recommendations": [], "patterns": pd.DataFrame()}

    for col in ["ctr_percent","average_percentage_viewed","average_view_duration_seconds","views","impressions"]:
        work[col] = pd.to_numeric(work[col], errors="coerce")

    med_apv = float(work["average_percentage_viewed"].median())
    ctr_work = work[work["ctr_percent"].notna()].copy()
    med_ctr = float(ctr_work["ctr_percent"].median()) if not ctr_work.empty else None

    def maturity(row):
        views = 0.0 if pd.isna(row.get("views")) else float(row.get("views"))
        imp = 0.0 if pd.isna(row.get("impressions")) else float(row.get("impressions"))
        if views >= 100 or imp >= 1000:
            return "MATURE"
        if views >= 30 or imp >= 300:
            return "DEVELOPING"
        return "EARLY"

    def base_diagnosis(row):
        apv_good = float(row["average_percentage_viewed"]) >= med_apv
        ctr = row.get("ctr_percent")
        if pd.isna(ctr) or med_ctr is None:
            return "CONTENT STRONG · CTR PENDING" if apv_good else "CONTENT HOLD OPPORTUNITY · CTR PENDING"
        ctr_good = float(ctr) >= med_ctr
        if ctr_good and apv_good:
            return "STRONG"
        if (not ctr_good) and apv_good:
            return "PACKAGING OPPORTUNITY"
        if ctr_good and (not apv_good):
            return "CONTENT HOLD OPPORTUNITY"
        return "PACKAGING + CONTENT"

    work["evidence_maturity"] = work.apply(maturity, axis=1)
    work["base_diagnosis"] = work.apply(base_diagnosis, axis=1)
    work["diagnosis"] = work["base_diagnosis"]
    work.loc[work["evidence_maturity"] == "EARLY", "diagnosis"] = "EARLY SIGNAL"

    apv_rank = work["average_percentage_viewed"].rank(pct=True)
    avd_rank = work["average_view_duration_seconds"].rank(pct=True)
    ctr_rank = work["ctr_percent"].rank(pct=True)
    has_ctr = work["ctr_percent"].notna()
    # Content-only score while CTR is pending; combined score once packaging data exists.
    work["learning_score"] = (apv_rank.fillna(0.5) * 0.80 + avd_rank.fillna(0.5) * 0.20) * 100.0
    work.loc[has_ctr, "learning_score"] = (
        ctr_rank[has_ctr].fillna(0.5) * 0.45 +
        apv_rank[has_ctr].fillna(0.5) * 0.45 +
        avd_rank[has_ctr].fillna(0.5) * 0.10
    ) * 100.0

    mature_learning = work[work["evidence_maturity"] != "EARLY"].copy()
    counts = mature_learning["base_diagnosis"].value_counts().to_dict()
    content_pending = mature_learning[mature_learning["ctr_percent"].isna()]
    summary = {
        "videos_analyzed": int(len(work)),
        "videos_learning_eligible": int(len(mature_learning)),
        "videos_with_ctr": int(work["ctr_percent"].notna().sum()),
        "ctr_pending": int(work["ctr_percent"].isna().sum()),
        "early_signal": int((work["evidence_maturity"] == "EARLY").sum()),
        "developing": int((work["evidence_maturity"] == "DEVELOPING").sum()),
        "mature": int((work["evidence_maturity"] == "MATURE").sum()),
        "median_ctr": med_ctr,
        "median_apv": med_apv,
        "strong": int(counts.get("STRONG", 0)),
        "content_strong_pending": int(counts.get("CONTENT STRONG · CTR PENDING", 0)),
        "packaging": int(counts.get("PACKAGING OPPORTUNITY", 0)),
        "content_hold": int(counts.get("CONTENT HOLD OPPORTUNITY", 0)),
        "content_hold_pending": int(counts.get("CONTENT HOLD OPPORTUNITY · CTR PENDING", 0)),
        "both": int(counts.get("PACKAGING + CONTENT", 0)),
    }

    recs = []
    if summary["early_signal"]:
        recs.append(
            f"{summary['early_signal']} video(s) are Early Signal only and are excluded from mature winner references."
        )
    if summary["ctr_pending"]:
        recs.append(
            f"CTR is still pending for {summary['ctr_pending']} video(s). Content learning continues from Average % Viewed, AVD and retention; "
            "packaging diagnosis will fill in automatically as YouTube Reporting reach reports arrive."
        )
    if summary["packaging"]:
        recs.append(
            f"{summary['packaging']} learning-eligible video(s) hold viewers relatively well but have below-median CTR. "
            "Prioritize title/thumbnail testing before changing the core content."
        )
    content_hold_total = summary["content_hold"] + summary["content_hold_pending"]
    if content_hold_total:
        recs.append(
            f"{content_hold_total} learning-eligible video(s) are below the channel median for Average % Viewed. "
            "Study opening, promise delivery, pacing and transitions; CTR is not required for this content diagnosis."
        )
    if summary["both"]:
        recs.append(
            f"{summary['both']} learning-eligible video(s) are below both current CTR and Average % Viewed medians. "
            "Treat them as full packaging + content review candidates."
        )
    if summary["strong"] or summary["content_strong_pending"]:
        recs.append(
            f"{summary['strong'] + summary['content_strong_pending']} learning-eligible video(s) currently hold viewers at or above the channel median. "
            "Use them as content references; videos with CTR data can also qualify as full packaging winners."
        )

    def title_flags(title):
        t = str(title or "").lower()
        return {
            "After/Over age framing": bool(re.search(r"\b(after|over)\s+(60|70)\b", t)),
            "Number/list framing": bool(re.search(r"(^|\s)\d+\b", t)),
            "Question framing": "?" in t,
            "Mistake framing": "mistake" in t or "mistakes" in t,
            "Warning framing": "warning" in t or "warnings" in t or "avoid" in t,
            "Action framing": any(k in t for k in ["do this", "try this", "add this", "start with", "eat this", "drink this"]),
        }

    eligible = mature_learning.copy()
    pattern_rows = []
    if not eligible.empty:
        flags = eligible["title"].apply(title_flags)
        for name in title_flags("").keys():
            mask = flags.apply(lambda d: d[name])
            subset = eligible[mask]
            if len(subset) < 2:
                continue
            content_strong_mask = subset["average_percentage_viewed"] >= med_apv
            ctr_subset = subset[subset["ctr_percent"].notna()]
            pattern_rows.append({
                "Pattern": name,
                "Videos": int(len(subset)),
                "Avg CTR %": float(ctr_subset["ctr_percent"].mean()) if not ctr_subset.empty else None,
                "Avg % Viewed": float(subset["average_percentage_viewed"].mean()),
                "Strong Rate %": float(content_strong_mask.mean() * 100.0),
                "CTR Videos": int(len(ctr_subset)),
            })

    patterns = pd.DataFrame(pattern_rows)
    if not patterns.empty:
        patterns = patterns.sort_values(
            ["Strong Rate %", "Videos"],
            ascending=[False, False]
        ).reset_index(drop=True)

    return {
        "videos": work,
        "summary": summary,
        "recommendations": recs,
        "patterns": patterns,
    }


def _retention_column(df: pd.DataFrame, aliases: list[str]) -> str | None:
    norm = {
        re.sub(r"[^a-z0-9]+", "", str(c).lower()): c
        for c in df.columns
    }
    for alias in aliases:
        key = re.sub(r"[^a-z0-9]+", "", alias.lower())
        if key in norm:
            return norm[key]
    return None


def _parse_retention_time(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    # Handle HH:MM:SS / MM:SS / seconds.
    return _parse_time(s)


def _scene_duration_seconds(db_path: Path, analytics_id: str) -> float | None:
    """Return the best duration for converting retention position to time.

    Prefer YouTube's Content/Performance `Duration` for the video when available.
    The production timeline can be slightly longer because of edit padding/outro material,
    so using MAX(scene.end_sec) alone can shift every retention point.
    Fall back to the stored scene/transcript duration when YouTube duration is unavailable.
    """
    with _db_connect(db_path) as con:
        perf = con.execute(
            """
            SELECT raw_json FROM performance_snapshots
            WHERE analytics_id=? AND report_kind='performance'
            ORDER BY imported_at DESC, id DESC LIMIT 1
            """,
            (analytics_id,),
        ).fetchone()
        if perf and perf["raw_json"]:
            try:
                raw = json.loads(perf["raw_json"])
                yt_duration = _duration_seconds(_col(raw, ["Duration", "Video duration", "duration_sec"]))
                if yt_duration is not None and yt_duration > 0:
                    return float(yt_duration)
            except Exception:
                pass

        row = con.execute(
            "SELECT MAX(end_sec) AS max_end FROM scene_snapshots WHERE analytics_id=?",
            (analytics_id,),
        ).fetchone()
    if not row or row["max_end"] is None:
        return None
    return float(row["max_end"])


def import_retention_curve(
    db_path: Path,
    analytics_id: str,
    df: pd.DataFrame,
    *,
    source_file: str = "",
) -> dict[str, Any]:
    """
    Import a true time/position retention curve for one video.

    Accepted shapes include:
      time/timestamp + retention %
      video position % + retention %
      both time and position + retention %

    A normal Content/Performance file containing only Average percentage viewed
    is explicitly rejected because it is not a retention curve.
    """
    init_db(db_path)
    if df is None or df.empty:
        raise AnalyticsDBError("Retention file has no rows.")

    avg_apv_col = _retention_column(df, ["Average percentage viewed (%)", "Average percentage viewed"])
    retention_col = _retention_column(df, [
        "Audience retention (%)",
        "Audience retention",
        "Retention (%)",
        "Retention",
        "Absolute audience retention (%)",
        "Relative retention (%)",
        "Relative retention",
    ])
    time_col = _retention_column(df, [
        "Video time",
        "Time",
        "Timestamp",
        "Elapsed video time",
        "Elapsed time",
        "Video time (seconds)",
        "Time (seconds)",
        "Seconds",
    ])
    position_col = _retention_column(df, [
        "Video position (%)",
        "Video position",
        "Position (%)",
        "Position",
        "Relative position (%)",
        "Elapsed video percentage (%)",
        "Elapsed video percentage",
    ])

    if retention_col is None:
        if avg_apv_col is not None:
            raise AnalyticsDBError(
                "This is a summary Content/Performance file. 'Average percentage viewed (%)' "
                "is not a timestamp-by-timestamp audience-retention curve."
            )
        raise AnalyticsDBError(
            "Could not find an audience-retention percentage column."
        )
    if time_col is None and position_col is None:
        raise AnalyticsDBError(
            "Retention curve needs video time/timestamp or video position (%)."
        )

    duration_sec = _scene_duration_seconds(db_path, analytics_id)
    if duration_sec is None or duration_sec <= 0:
        raise AnalyticsDBError(
            "No stored Actual Timeline or timestamped transcript is available for this video. "
            "Attach the timeline/transcript first, then import retention."
        )

    # Detect the position scale ONCE for the whole file. YouTube exports can use
    # either 0..99/100 or 0..0.99/1.0. The previous row-by-row test incorrectly
    # turned only positions 0 and 1 into 0 and 100 in a 0..99 file, which created
    # a false terminal spike.
    position_scale = 1.0
    if position_col is not None:
        parsed_positions = [
            _num(v, percent=True) for v in df[position_col].tolist()
        ]
        parsed_positions = [v for v in parsed_positions if v is not None]
        if parsed_positions and max(parsed_positions) <= 1.5:
            position_scale = 100.0

    raw_rows = []
    for _, row in df.iterrows():
        d = row.to_dict()
        ret = _num(d.get(retention_col), percent=True)
        if ret is None:
            continue

        t = _parse_retention_time(d.get(time_col)) if time_col else None
        pos = _num(d.get(position_col), percent=True) if position_col else None
        if pos is not None:
            pos *= position_scale

        if t is None and pos is not None:
            t = max(0.0, min(duration_sec, (pos / 100.0) * duration_sec))
        if pos is None and t is not None:
            pos = max(0.0, min(100.0, (t / duration_sec) * 100.0))

        if t is None or pos is None:
            continue
        raw_rows.append((float(t), float(pos), float(ret)))

    if len(raw_rows) < 2:
        raise AnalyticsDBError(
            "Retention file did not contain enough valid curve points."
        )

    # Detect ratio-style retention values (0..1) and convert to percent.
    ret_values = [r[2] for r in raw_rows]
    if max(ret_values) <= 1.5:
        raw_rows = [(t, p, r * 100.0) for t, p, r in raw_rows]

    # Keep only sane, sorted points.
    cleaned = []
    for t, p, r in raw_rows:
        if t < 0 or p < 0 or p > 100.5 or r < 0:
            continue
        cleaned.append((t, p, r))
    cleaned.sort(key=lambda x: x[0])

    if len(cleaned) < 2:
        raise AnalyticsDBError("No valid retention points remained after validation.")

    imported_at = datetime.now().isoformat(timespec="microseconds")
    with _db_connect(db_path) as con:
        # Current retention curve replaces the previous curve for this video.
        # This prevents duplicate points from repeated imports.
        con.execute("DELETE FROM retention_points WHERE analytics_id=?", (analytics_id,))
        con.executemany(
            """
            INSERT INTO retention_points(
                analytics_id, imported_at, source_file, time_sec, position_percent, retention_percent
            ) VALUES(?,?,?,?,?,?)
            """,
            [
                (analytics_id, imported_at, source_file, t, p, r)
                for t, p, r in cleaned
            ],
        )
        con.execute(
            """
            UPDATE videos
            SET retention_status='available', updated_at=?
            WHERE analytics_id=?
            """,
            (_now(), analytics_id),
        )

    _invalidate_retention_mapping_cache(db_path, analytics_id)
    return {
        "points": len(cleaned),
        "time_column": time_col,
        "position_column": position_col,
        "retention_column": retention_col,
        "duration_sec": duration_sec,
        "source_file": source_file,
    }


def retention_points_df(db_path: Path, analytics_id: str) -> pd.DataFrame:
    init_db(db_path)
    with _db_connect(db_path) as con:
        rows = con.execute(
            """
            SELECT time_sec, position_percent, retention_percent, imported_at, source_file
            FROM retention_points
            WHERE analytics_id=?
            ORDER BY time_sec
            """,
            (analytics_id,),
        ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def production_provenance(db_path: Path, analytics_id: str) -> dict[str, Any]:
    """Verify canonical SEO production archive for one analytics identity."""
    db_path = Path(db_path)
    archive_dir = db_path.parent / "project_assets" / str(analytics_id)
    snapshot_path = archive_dir / "production_timeline_snapshot.csv"
    result: dict[str, Any] = {
        "analytics_id": str(analytics_id),
        "archive_dir": str(archive_dir.resolve()),
        "snapshot_path": str(snapshot_path.resolve()),
        "archive_found": archive_dir.is_dir(),
        "snapshot_found": snapshot_path.is_file(),
        "verified": False,
        "reason": "",
        "scene_count": 0,
    }
    if not archive_dir.is_dir():
        result["reason"] = "Project assets folder is missing."
        return result
    if not snapshot_path.is_file():
        result["reason"] = "production_timeline_snapshot.csv is missing."
        return result
    try:
        snap = pd.read_csv(snapshot_path)
    except Exception as exc:
        result["reason"] = f"Production snapshot could not be read: {exc}"
        return result
    required = {"scene_id", "actual_start_sec", "actual_end_sec", "timing_authority"}
    missing = sorted(required - set(snap.columns))
    if missing:
        result["reason"] = "Production snapshot is missing required column(s): " + ", ".join(missing)
        return result
    ids = snap["scene_id"].fillna("").astype(str).str.strip()
    if snap.empty or (ids == "").any() or ids.duplicated().any():
        result["reason"] = "Production snapshot has empty/duplicate Scene IDs or no scenes."
        return result
    authorities = snap["timing_authority"].fillna("").astype(str).str.strip()
    if not (authorities == "08_actual_timeline.csv").all():
        result["reason"] = "Production snapshot timing authority is not 08_actual_timeline.csv for every scene."
        return result

    # At least one canonical production metadata column must be present.
    def prefixed_candidates(names: list[str]) -> list[str]:
        wanted = {("production_" + n).lower().replace(" ", "_") for n in names}
        return [c for c in snap.columns if c.lower().replace(" ", "_") in wanted]
    asset_cols = prefixed_candidates(["recommended_asset_type", "asset_type", "asset_status", "Asset Type"])
    visual_cols = prefixed_candidates(["visual_mode", "Visual Mode"])
    overlay_cols = prefixed_candidates(["overlay_type", "Overlay Type"])
    if not (asset_cols or visual_cols or overlay_cols):
        result["reason"] = "Production snapshot contains no canonical production metadata columns."
        return result
    result["verified"] = True
    result["reason"] = "Verified canonical SEO production snapshot."
    result["scene_count"] = int(len(snap))
    result["_snapshot_df"] = snap
    result["_asset_cols"] = asset_cols
    result["_visual_cols"] = visual_cols
    result["_overlay_cols"] = overlay_cols
    return result


def _verified_production_metadata(db_path: Path, analytics_id: str) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    prov = production_provenance(db_path, analytics_id)
    if not prov.get("verified"):
        return prov, {}
    snap = prov.pop("_snapshot_df")
    asset_cols = prov.pop("_asset_cols")
    visual_cols = prov.pop("_visual_cols")
    overlay_cols = prov.pop("_overlay_cols")

    def first_value(row: pd.Series, cols: list[str]) -> str | None:
        for col in cols:
            value = row.get(col)
            if pd.notna(value) and str(value).strip():
                return str(value).strip()
        return None

    meta: dict[str, dict[str, Any]] = {}
    for _, row in snap.iterrows():
        sid = str(row.get("scene_id") or "").strip()
        meta[sid] = {
            "visual_mode": first_value(row, visual_cols),
            "asset_type": first_value(row, asset_cols),
            "overlay_type": first_value(row, overlay_cols),
            "actual_start_sec": float(row.get("actual_start_sec")),
            "actual_end_sec": float(row.get("actual_end_sec")),
        }
    return prov, meta


def _apply_production_provenance_gate(db_path: Path, analytics_id: str, mapped: pd.DataFrame) -> pd.DataFrame:
    """Never expose stale SQLite production fields as verified production metadata."""
    if mapped is None or mapped.empty:
        return mapped
    out = mapped.copy()
    prov, meta = _verified_production_metadata(db_path, analytics_id)
    for col in ("visual_mode", "asset_type", "overlay_type"):
        out[col] = None
    out["production_provenance"] = "UNVERIFIED"
    if not prov.get("verified"):
        return out

    verified_rows = 0
    for idx, row in out.iterrows():
        sid = str(row.get("scene_id") or "").strip()
        m = meta.get(sid)
        if not m:
            continue
        # Exact scene timing protects against a stale/wrong snapshot with the same Scene IDs.
        try:
            same_start = abs(float(row.get("start_sec")) - float(m["actual_start_sec"])) < 0.05
            same_end = abs(float(row.get("end_sec")) - float(m["actual_end_sec"])) < 0.05
        except Exception:
            same_start = same_end = False
        if not (same_start and same_end):
            continue
        for col in ("visual_mode", "asset_type", "overlay_type"):
            out.at[idx, col] = m.get(col)
        out.at[idx, "production_provenance"] = "VERIFIED"
        verified_rows += 1
    return out

def scene_retention_mapping(db_path: Path, analytics_id: str) -> pd.DataFrame:
    """
    Map stored retention points to S### Actual Timeline scenes or TS#### transcript segments.

    Output includes retention at scene start/end, scene average, delta across the scene,
    and a relative diagnostic based on the channel/video curve.
    """
    cached = _retention_mapping_cache_df(db_path, analytics_id)
    if not cached.empty:
        gated = _apply_production_provenance_gate(db_path, analytics_id, cached)
        sync_production_learning_scenes(db_path, analytics_id, mapped=gated)
        return gated

    scenes = scene_snapshot_df(db_path, analytics_id)
    points = retention_points_df(db_path, analytics_id)
    if scenes.empty or points.empty:
        return pd.DataFrame()

    scenes = scenes.copy()
    points = points.copy()
    points["time_sec"] = pd.to_numeric(points["time_sec"], errors="coerce")
    points["retention_percent"] = pd.to_numeric(points["retention_percent"], errors="coerce")
    points = points.dropna(subset=["time_sec","retention_percent"]).sort_values("time_sec")
    if points.empty:
        return pd.DataFrame()

    times = points["time_sec"].to_numpy()
    vals = points["retention_percent"].to_numpy()

    def interp(t: float) -> float:
        import numpy as np
        return float(np.interp(float(t), times, vals))

    rows = []
    for _, s in scenes.sort_values("ordinal").iterrows():
        start = pd.to_numeric(pd.Series([s.get("start_sec")]), errors="coerce").iloc[0]
        end = pd.to_numeric(pd.Series([s.get("end_sec")]), errors="coerce").iloc[0]
        if pd.isna(start) or pd.isna(end) or float(end) <= float(start):
            continue
        start = float(start)
        end = float(end)

        start_r = interp(start)
        end_r = interp(end)
        in_scene = points[
            (points["time_sec"] >= start) &
            (points["time_sec"] <= end)
        ]
        avg_r = float(in_scene["retention_percent"].mean()) if not in_scene.empty else (start_r + end_r) / 2.0
        delta = end_r - start_r

        rows.append({
            "scene_id": s.get("scene_id"),
            "source": s.get("source"),
            "start_sec": start,
            "end_sec": end,
            "duration_sec": s.get("duration_sec"),
            "script_text": s.get("script_text"),
            "visual_mode": s.get("visual_mode"),
            "asset_type": s.get("asset_type"),
            "overlay_type": s.get("overlay_type"),
            "retention_start": start_r,
            "retention_end": end_r,
            "retention_avg": avg_r,
            "retention_delta": delta,
        })

    out = pd.DataFrame(rows)
    if out.empty:
        return out

    # Relative thresholds are video-specific and robust to scale.
    median_delta = float(out["retention_delta"].median())
    q25_delta = float(out["retention_delta"].quantile(0.25))
    q75_delta = float(out["retention_delta"].quantile(0.75))
    median_avg = float(out["retention_avg"].median())

    def label(row):
        d = float(row["retention_delta"])
        a = float(row["retention_avg"])
        if d <= q25_delta and d < -1.0:
            return "DROP"
        if d >= q75_delta and d > 1.0:
            return "SPIKE / RECOVERY"
        if a < median_avg and d < 0:
            return "WEAK HOLD"
        return "STABLE"

    out["retention_signal"] = out.apply(label, axis=1)

    # Rank problem scenes: strongest negative movement first, then lower average.
    out["problem_score"] = (-out["retention_delta"].clip(upper=0) * 0.7) + ((median_avg - out["retention_avg"]).clip(lower=0) * 0.3)
    out = out.sort_values("start_sec").reset_index(drop=True)
    _store_retention_mapping_cache(db_path, analytics_id, out)
    out = _apply_production_provenance_gate(db_path, analytics_id, out)
    sync_production_learning_scenes(db_path, analytics_id, mapped=out)
    return out


def sync_production_learning_scenes(
    db_path: Path, analytics_id: str, *, mapped: pd.DataFrame | None = None
) -> dict[str, int]:
    """Persist scene-level production + retention evidence for cross-video learning.

    This stores observations only. It never promotes or activates a production rule.
    Rows without real production metadata are deliberately excluded so transcript-only
    historical videos cannot fabricate AVATAR/AI_IMAGE/OVERLAY evidence.
    """
    init_db(db_path)
    provenance = production_provenance(db_path, analytics_id)
    if not provenance.get("verified"):
        with _db_connect(db_path) as con:
            con.execute("DELETE FROM production_learning_scenes WHERE analytics_id=?", (analytics_id,))
        return {"stored": 0, "skipped_no_metadata": 0, "blocked_unverified": 1}
    if mapped is None:
        mapped = scene_retention_mapping(db_path, analytics_id)
    if mapped is None or mapped.empty:
        return {"stored": 0, "skipped_no_metadata": 0}

    rows = []
    skipped = 0
    for _, r in mapped.iterrows():
        if str(r.get("production_provenance") or "").strip() != "VERIFIED":
            skipped += 1
            continue
        asset = str(r.get("asset_type") or "").strip()
        visual = str(r.get("visual_mode") or "").strip()
        overlay = str(r.get("overlay_type") or "").strip()
        if not (asset or visual or overlay):
            skipped += 1
            continue
        rows.append((
            analytics_id, str(r.get("scene_id") or "").strip(),
            float(r.get("start_sec")), float(r.get("end_sec")),
            float(r.get("duration_sec")) if pd.notna(r.get("duration_sec")) else None,
            str(r.get("script_text") or "").strip() or None,
            visual or None, asset or None, overlay or None,
            float(r.get("retention_start")) if pd.notna(r.get("retention_start")) else None,
            float(r.get("retention_end")) if pd.notna(r.get("retention_end")) else None,
            float(r.get("retention_avg")) if pd.notna(r.get("retention_avg")) else None,
            float(r.get("retention_delta")) if pd.notna(r.get("retention_delta")) else None,
            str(r.get("retention_signal") or "").strip() or None,
            "OBSERVATION", "actual_timeline_retention", _now(),
        ))
    with _db_connect(db_path) as con:
        con.execute("DELETE FROM production_learning_scenes WHERE analytics_id=?", (analytics_id,))
        if rows:
            con.executemany(
                """
                INSERT INTO production_learning_scenes(
                    analytics_id,scene_id,start_sec,end_sec,duration_sec,script_text,
                    visual_mode,asset_type,overlay_type,retention_start,retention_end,
                    retention_avg,retention_delta,retention_signal,evidence_status,source,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, rows
            )
    return {"stored": len(rows), "skipped_no_metadata": skipped}


def production_learning_scene_df(db_path: Path, analytics_id: str | None = None) -> pd.DataFrame:
    init_db(db_path)
    sql = "SELECT * FROM production_learning_scenes"
    params: tuple[Any, ...] = ()
    if analytics_id:
        sql += " WHERE analytics_id=?"
        params = (analytics_id,)
    sql += " ORDER BY analytics_id,start_sec"
    with _db_connect(db_path) as con:
        rows = con.execute(sql, params).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def production_learning_summary(db_path: Path, *, min_videos: int = 1) -> pd.DataFrame:
    """Cross-video descriptive evidence only; verified canonical archives only."""
    # Purge legacy/polluted production-learning rows whose analytics identity no
    # longer has a verified canonical SEO production snapshot.
    init_db(db_path)
    with _db_connect(db_path) as con:
        ids = [str(r[0]) for r in con.execute(
            "SELECT DISTINCT analytics_id FROM production_learning_scenes"
        ).fetchall()]
    unverified = [aid for aid in ids if not production_provenance(db_path, aid).get("verified")]
    if unverified:
        with _db_connect(db_path) as con:
            con.executemany(
                "DELETE FROM production_learning_scenes WHERE analytics_id=?",
                [(aid,) for aid in unverified],
            )
    df = production_learning_scene_df(db_path)
    if df.empty:
        return pd.DataFrame()
    df = df[df["asset_type"].fillna("").astype(str).str.strip() != ""].copy()
    if df.empty:
        return pd.DataFrame()
    df["retention_delta"] = pd.to_numeric(df["retention_delta"], errors="coerce")
    df["retention_avg"] = pd.to_numeric(df["retention_avg"], errors="coerce")
    grouped = df.groupby(["asset_type", "visual_mode"], dropna=False)
    out = grouped.agg(
        videos=("analytics_id", "nunique"),
        scenes=("scene_id", "count"),
        avg_retention_delta=("retention_delta", "mean"),
        median_retention_delta=("retention_delta", "median"),
        avg_retention=("retention_avg", "mean"),
    ).reset_index()
    sig = grouped["retention_signal"].value_counts().unstack(fill_value=0).reset_index()
    out = out.merge(sig, on=["asset_type","visual_mode"], how="left")
    out = out[out["videos"] >= int(min_videos)].copy()
    out["pattern_status"] = out["videos"].map(lambda n: "CHANNEL PATTERN CANDIDATE" if n >= 3 else ("REPEATED SIGNAL" if n >= 2 else "OBSERVATION"))
    return out.sort_values(["videos","scenes"], ascending=[False,False]).reset_index(drop=True)


def script_retention_learning(db_path: Path, analytics_id: str, limit: int = 12) -> pd.DataFrame:
    """Map meaningful retention losses to nearby spoken words and produce cautious hypotheses.

    Retention identifies WHERE viewers weakened. Transcript/timeline context is then used to
    classify WHAT kind of passage was present. The classifier must not pretend a retention
    drop proves causality: when the wording does not support a specific diagnosis it returns
    CAUSE UNCERTAIN instead of forcing a generic explanation.

    No fixed re-hook timer or per-N-second writing quota is prescribed here.
    """
    mapped = scene_retention_mapping(db_path, analytics_id)
    if mapped.empty:
        return pd.DataFrame()
    m = mapped.sort_values('start_sec').reset_index(drop=True).copy()
    video_end = float(pd.to_numeric(m['end_sec'], errors='coerce').max() or 0.0)

    # Build contiguous analysis windows from the stored scene/transcript rows. The window is
    # only an analysis unit; it is not a writing cadence recommendation.
    windows=[]; bucket=[]; wstart=None
    for _, r in m.iterrows():
        if wstart is None:
            wstart=float(r['start_sec'])
        bucket.append(r)
        if float(r['end_sec']) - wstart >= 30:
            windows.append(bucket); bucket=[]; wstart=None
    if bucket:
        windows.append(bucket)

    def clean_text(rows):
        t=' '.join(str(x.get('script_text') or '').strip() for x in rows).strip()
        return re.sub(r'\s+', ' ', t)

    def nearby_text(start_sec, end_sec, before=25, after=15):
        rows=m[(m['end_sec'] >= max(0,start_sec-before)) & (m['start_sec'] <= end_sec+after)]
        return clean_text([r for _,r in rows.iterrows()])

    def lexical_repetition_score(text: str) -> float:
        # Conservative signal: repeated 3-5 word phrases, not merely a low unique-word ratio.
        tokens=[x.lower() for x in re.findall(r"\b[a-zA-Z][a-zA-Z'-]*\b", text)]
        if len(tokens) < 35:
            return 0.0
        grams=[]
        for n in (3,4,5):
            grams.extend(tuple(tokens[i:i+n]) for i in range(0, max(0, len(tokens)-n+1)))
        if not grams:
            return 0.0
        from collections import Counter
        counts=Counter(grams)
        repeated=sum(c-1 for c in counts.values() if c > 1)
        return repeated / max(1, len(grams))

    def diagnose(text, context, start, end, words, dur):
        low=text.lower(); ctx=context.lower()
        question_count=text.count('?')
        wps=words/max(1.0,dur)
        late_fraction=(start/video_end) if video_end > 0 else 0.0

        delay_phrases=[
            'before we','before i','but before','first, let','first let',
            'we need to understand','before we go further','before getting to','before getting into'
        ]
        caveat_phrases=[
            'however','it depends','may or may not','not necessarily','not a diagnosis',
            'not a cure','cannot','can’t promise',"can't promise",'does not mean','doesn’t mean'
        ]
        safety_phrases=[
            'ask your doctor','talk to your doctor','seek medical','healthcare professional',
            'clinician','symptoms are new','symptoms are worsening','urgent care','emergency care'
        ]
        explicit_repeat_phrases=[
            'in other words','to put it another way','again,','as i mentioned','as we said',
            'as i said','let me repeat','the same point'
        ]
        transition_phrases=[
            'now let us switch','now let’s switch','on another note','separately,',
            'another thing entirely','before we move on','let us move on','let’s move on'
        ]
        setup_phrases=[
            'here is some background','a little background','to understand why',
            'there are a few things to know','let us start with the basics','let’s start with the basics'
        ]
        cta_phrases=[
            'subscribe','like this video','leave a comment','comment below','share this video',
            'thanks for watching','thank you for watching','see you in the next'
        ]
        payoff_phrases=[
            'here is the answer','here’s the answer','the key is','the important point is',
            'what helps is','what matters is','the first thing','the practical step'
        ]

        # Ending/CTA is a distinct, often-normal behavior. Do not convert it into a writing defect.
        if late_fraction >= 0.82 and any(x in low for x in cta_phrases):
            return (
                'CTA / ending exit',
                'The drop occurs near the end while the passage is asking for an action or closing the video; some viewer exit here can be normal.',
                'Keep the ending concise and place the final viewer value before or alongside the CTA; do not treat normal end-of-video exit as a content failure.'
            )

        if start < 60 and any(x in low for x in delay_phrases):
            return (
                'Delayed payoff / preamble in the opening',
                'The opening contains a setup/detour phrase while viewers are still waiting for the core promised value.',
                'Deliver a concrete piece of the promised value earlier, then add only the setup or qualification needed to understand it.'
            )

        if start < 60 and question_count >= 2 and not any(x in low for x in payoff_phrases):
            return (
                'Opening self-assessment may delay the payoff',
                f'This opening window asks {question_count} questions while retention is weakening and no clear payoff phrase is present.',
                'Use the minimum recognition needed for self-identification, then advance to the promised answer or first useful insight.'
            )

        caveat_hits=sum(1 for x in caveat_phrases if x in low)
        safety_hits=sum(1 for x in safety_phrases if x in low)
        if caveat_hits >= 2 or (caveat_hits >= 1 and safety_hits >= 1):
            return (
                'Qualification / safety interruption',
                'Several qualifying or safety-oriented phrases cluster inside the same weakening passage.',
                'Preserve required safety context, but make the useful point easy to identify and avoid duplicating the same qualification.'
            )

        repetition_score=lexical_repetition_score(text)
        if any(x in low for x in explicit_repeat_phrases) or repetition_score >= 0.055:
            return (
                'Repetition / restatement signal',
                'The wording contains explicit restatement language or repeated multi-word phrases while retention weakens.',
                'Remove redundant restatement and keep the next sentence only when it adds a new distinction, example, consequence, or action.'
            )

        if any(x in low for x in setup_phrases) and not any(x in low for x in payoff_phrases):
            return (
                'Low-information setup before the next payoff',
                'The weakening passage is framed as background/basics and does not contain a clear payoff marker.',
                'Compress background to the minimum needed and attach it directly to the next concrete takeaway.'
            )

        if any(x in low for x in transition_phrases):
            return (
                'Transition / possible topic shift',
                'The weakening passage contains an explicit move-on or topic-switch phrase.',
                'Make the connection to the main promise explicit before changing subtopic, and remove transitions that do not advance that promise.'
            )

        if safety_hits >= 1:
            return (
                'Care / safety section may be interrupting momentum',
                'The weakening passage is dominated by care or safety guidance.',
                'Keep required safety guidance intact, but make it concise, non-repetitive, and clearly connected to the practical point around it.'
            )

        # Very dense delivery is a passage characteristic, not proof of why viewers left.
        if wps > 3.25 and words >= 70:
            return (
                'Dense information delivery',
                f'This passage is unusually dense at roughly {wps:.1f} words/second while retention is weakening.',
                'Reduce simultaneous ideas and make the hierarchy clearer; preserve the strongest takeaway and supporting evidence.'
            )

        # A large early drop with no stronger textual cue should be surfaced as a hook/promise
        # weakness hypothesis rather than mislabeled repetition.
        if start < 60:
            return (
                'Opening / hook hold weakness — cause uncertain',
                'Retention falls in the opening, but the transcript does not contain enough evidence to attribute the loss to one specific wording problem.',
                'Review whether the opening quickly confirms the title promise, establishes relevance, and gives useful value; do not change it based on this video alone.'
            )

        return (
            'CAUSE UNCERTAIN',
            'Retention weakened here, but the nearby transcript does not provide enough evidence to identify a specific script cause reliably.',
            'Do not create a writing rule from this event alone. Compare the same kind of passage across multiple videos and investigate only repeated patterns.'
        )

    rows=[]
    median_avg=float(m['retention_avg'].median())
    for b in windows:
        start=float(b[0]['start_sec']); end=float(b[-1]['end_sec'])
        rs=float(b[0]['retention_start']); retn=float(b[-1]['retention_end']); delta=retn-rs
        text=clean_text(b); dur=max(1.0,end-start)
        words=len(re.findall(r"\b[\w’'-]+\b", text))
        if start < 45:
            severity='MAJOR OPENING LOSS' if delta <= -12 else ('OPENING LOSS' if delta <= -6 else 'OPENING HOLD')
        else:
            severity='MAJOR DROP' if delta <= -5 else ('DROP' if delta <= -2.5 else ('WEAK HOLD' if retn < median_avg and delta < -1 else 'STABLE'))
        if severity in ('STABLE','OPENING HOLD'):
            continue
        context=nearby_text(start,end)
        issue,evidence,rule=diagnose(text,context,start,end,words,dur)
        rows.append({
            'start_sec':start,'end_sec':end,'retention_start':rs,'retention_end':retn,
            'retention_delta':delta,'event':severity,'script_text':text,
            'primary_issue':issue,'evidence':evidence,'future_rule':rule,
            'context_text':context,'word_count':words
        })
    if not rows:
        return pd.DataFrame()
    out=pd.DataFrame(rows)
    out['priority_score']=(-out['retention_delta'].clip(upper=0)) + out['event'].isin(['MAJOR OPENING LOSS','MAJOR DROP']).astype(int)*3
    return out.sort_values(['priority_score','start_sec'], ascending=[False,True]).head(int(limit)).reset_index(drop=True)

def retention_drop_summary(db_path: Path, analytics_id: str, limit: int = 10) -> pd.DataFrame:
    mapped = scene_retention_mapping(db_path, analytics_id)
    if mapped.empty:
        return mapped
    bad = mapped[mapped["retention_signal"].isin(["DROP","WEAK HOLD"])].copy()
    if bad.empty:
        return bad
    return bad.sort_values(
        ["problem_score","retention_delta"],
        ascending=[False, True]
    ).head(int(limit)).reset_index(drop=True)


def cross_video_script_pattern_learning(db_path: Path) -> dict[str, Any]:
    """
    Aggregate script-retention diagnoses across videos.

    Only videos with both a stored retention curve and timestamped content are considered.
    To avoid turning tiny samples into channel rules, the same Primary Script Issue must
    repeat across multiple videos before it is promoted beyond a watch signal.

    Rule confidence:
      WATCH            = seen in 1 learning-eligible video
      REPEATED SIGNAL  = seen in 2 learning-eligible videos
      CHANNEL PATTERN  = seen in 3+ learning-eligible videos

    Learning eligibility mirrors the current evidence-maturity idea:
      eligible when latest performance has >=30 views OR >=300 impressions.
    """
    init_db(db_path)

    dashboard = channel_dashboard_data(db_path)
    videos = dashboard.get("videos")
    if videos is None or videos.empty:
        return {
            "patterns": pd.DataFrame(),
            "events": pd.DataFrame(),
            "summary": {},
        }

    events = []
    for _, v in videos.iterrows():
        aid = v.get("analytics_id")
        if not aid:
            continue

        # Need actual retention + mapped content.
        points = retention_points_df(db_path, aid)
        scenes = scene_snapshot_df(db_path, aid)
        if points.empty or scenes.empty:
            continue

        views = pd.to_numeric(pd.Series([v.get("views")]), errors="coerce").iloc[0]
        impressions = pd.to_numeric(pd.Series([v.get("impressions")]), errors="coerce").iloc[0]
        views = 0.0 if pd.isna(views) else float(views)
        impressions = 0.0 if pd.isna(impressions) else float(impressions)
        learning_eligible = bool(views >= 30 or impressions >= 300)

        diagnoses = script_retention_learning(db_path, aid, limit=50)
        if diagnoses.empty:
            continue

        for _, d in diagnoses.iterrows():
            issue_text = str(d.get("primary_issue") or "").strip()
            # Uncertain diagnoses remain visible for per-video investigation but must never
            # become cross-video channel rules.
            promotable = "uncertain" not in issue_text.lower()
            events.append({
                "analytics_id": aid,
                "video_id": v.get("youtube_video_id"),
                "title": v.get("title"),
                "publish_date": v.get("publish_date"),
                "views": views,
                "impressions": impressions,
                "learning_eligible": learning_eligible,
                "event": d.get("event"),
                "primary_issue": d.get("primary_issue"),
                "future_rule": d.get("future_rule"),
                "promotable": promotable,
                "start_sec": d.get("start_sec"),
                "end_sec": d.get("end_sec"),
                "retention_delta": d.get("retention_delta"),
                "retention_start": d.get("retention_start"),
                "retention_end": d.get("retention_end"),
                "script_text": d.get("script_text"),
                "context_text": d.get("context_text"),
            })

    events_df = pd.DataFrame(events)
    if events_df.empty:
        return {
            "patterns": pd.DataFrame(),
            "events": events_df,
            "summary": {
                "videos_with_script_retention": 0,
                "learning_eligible_videos": 0,
                "channel_patterns": 0,
            },
        }

    eligible = events_df[
        events_df["learning_eligible"] & events_df["promotable"].fillna(False)
    ].copy()

    pattern_rows = []
    if not eligible.empty:
        for issue, grp in eligible.groupby("primary_issue", dropna=True):
            unique_videos = int(grp["analytics_id"].nunique())
            event_count = int(len(grp))
            avg_drop = float(pd.to_numeric(grp["retention_delta"], errors="coerce").mean())
            median_drop = float(pd.to_numeric(grp["retention_delta"], errors="coerce").median())
            opening_events = int(
                (
                    pd.to_numeric(grp["start_sec"], errors="coerce").fillna(999999) < 60
                ).sum()
            )
            opening_video_count = int(
                grp[
                    pd.to_numeric(grp["start_sec"], errors="coerce").fillna(999999) < 60
                ]["analytics_id"].nunique()
            )

            # Use the most common future rule attached to this issue.
            rules = grp["future_rule"].dropna().astype(str)
            if rules.empty:
                future_rule = ""
            else:
                future_rule = rules.value_counts().index[0]

            if unique_videos >= 3:
                confidence = "CHANNEL PATTERN"
            elif unique_videos == 2:
                confidence = "REPEATED SIGNAL"
            else:
                confidence = "WATCH"

            # Stronger priority for repeated cross-video events + larger losses.
            priority_score = (
                unique_videos * 10.0 +
                event_count * 2.0 +
                max(0.0, -avg_drop) +
                opening_video_count * 3.0
            )

            pattern_rows.append({
                "Script Pattern": str(issue),
                "Videos": unique_videos,
                "Events": event_count,
                "Avg Drop": avg_drop,
                "Median Drop": median_drop,
                "Opening Videos": opening_video_count,
                "Opening Events": opening_events,
                "Confidence": confidence,
                "Future Script Rule": future_rule,
                "Priority Score": priority_score,
            })

    patterns = pd.DataFrame(pattern_rows)
    if not patterns.empty:
        confidence_order = {
            "CHANNEL PATTERN": 3,
            "REPEATED SIGNAL": 2,
            "WATCH": 1,
        }
        patterns["_confidence_order"] = patterns["Confidence"].map(confidence_order).fillna(0)
        patterns = patterns.sort_values(
            ["_confidence_order", "Priority Score", "Videos", "Events"],
            ascending=[False, False, False, False],
        ).drop(columns=["_confidence_order"]).reset_index(drop=True)

    summary = {
        "videos_with_script_retention": int(events_df["analytics_id"].nunique()),
        "learning_eligible_videos": int(eligible["analytics_id"].nunique()) if not eligible.empty else 0,
        "early_only_videos": int(
            events_df.loc[~events_df["learning_eligible"], "analytics_id"].nunique()
        ),
        "channel_patterns": int(
            (patterns["Confidence"] == "CHANNEL PATTERN").sum()
        ) if not patterns.empty else 0,
        "repeated_signals": int(
            (patterns["Confidence"] == "REPEATED SIGNAL").sum()
        ) if not patterns.empty else 0,
        "watch_signals": int(
            (patterns["Confidence"] == "WATCH").sum()
        ) if not patterns.empty else 0,
    }

    return {
        "patterns": patterns,
        "events": events_df,
        "summary": summary,
    }


def _rule_key(pattern: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(pattern or "").lower()).strip("_") or "unnamed_rule"


def active_channel_script_rules(db_path: Path) -> pd.DataFrame:
    """Return currently ACTIVE channel-learned writing rules."""
    init_db(db_path)
    with _db_connect(db_path) as con:
        rows = con.execute(
            """
            SELECT rule_key, script_pattern, rule_text, status, videos, events,
                   avg_drop, median_drop, opening_videos, first_seen_at,
                   last_seen_at, activated_at, retired_at, evidence_json
            FROM channel_script_rules
            WHERE status='ACTIVE'
            ORDER BY videos DESC, events DESC, avg_drop ASC, script_pattern
            """
        ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def all_channel_script_rules(db_path: Path) -> pd.DataFrame:
    """Return the complete rule lifecycle for auditability."""
    init_db(db_path)
    with _db_connect(db_path) as con:
        rows = con.execute(
            """
            SELECT rule_key, script_pattern, rule_text, status, videos, events,
                   avg_drop, median_drop, opening_videos, first_seen_at,
                   last_seen_at, activated_at, retired_at, evidence_json
            FROM channel_script_rules
            ORDER BY
                CASE status
                    WHEN 'ACTIVE' THEN 1
                    WHEN 'EMERGING' THEN 2
                    WHEN 'OBSERVATION' THEN 3
                    WHEN 'RETIRED' THEN 4
                    ELSE 5
                END,
                videos DESC, events DESC, script_pattern
            """
        ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def sync_active_channel_script_rules(db_path: Path) -> dict[str, Any]:
    """
    Promote cross-video script findings through an automatic lifecycle:

      OBSERVATION = 1 learning-eligible video
      EMERGING    = 2 learning-eligible videos
      ACTIVE      = 3+ learning-eligible videos
      RETIRED     = previously known rule no longer supported by current evidence

    ACTIVE rules are the only ones allowed to auto-inject into future writing.
    """
    init_db(db_path)
    learned = cross_video_script_pattern_learning(db_path)
    patterns = learned.get("patterns")
    now = _now()

    current: dict[str, dict[str, Any]] = {}
    if patterns is not None and not patterns.empty:
        for _, row in patterns.iterrows():
            pattern = str(row.get("Script Pattern") or "").strip()
            if not pattern:
                continue
            videos = int(row.get("Videos") or 0)
            events = int(row.get("Events") or 0)
            if videos >= 3:
                status = "ACTIVE"
            elif videos == 2:
                status = "EMERGING"
            else:
                status = "OBSERVATION"

            key = _rule_key(pattern)
            evidence = {
                "videos": videos,
                "events": events,
                "avg_drop": None if pd.isna(row.get("Avg Drop")) else float(row.get("Avg Drop")),
                "median_drop": None if pd.isna(row.get("Median Drop")) else float(row.get("Median Drop")),
                "opening_videos": int(row.get("Opening Videos") or 0),
                "confidence": str(row.get("Confidence") or ""),
            }
            current[key] = {
                "script_pattern": pattern,
                "rule_text": str(row.get("Future Script Rule") or "").strip(),
                "status": status,
                "videos": videos,
                "events": events,
                "avg_drop": evidence["avg_drop"],
                "median_drop": evidence["median_drop"],
                "opening_videos": evidence["opening_videos"],
                "evidence_json": json.dumps(evidence, ensure_ascii=False),
            }

    with _db_connect(db_path) as con:
        existing_rows = con.execute(
            "SELECT * FROM channel_script_rules"
        ).fetchall()
        existing = {str(r["rule_key"]): dict(r) for r in existing_rows}

        activated = 0
        updated = 0
        retired = 0

        for key, item in current.items():
            old = existing.get(key)
            if old is None:
                activated_at = now if item["status"] == "ACTIVE" else None
                con.execute(
                    """
                    INSERT INTO channel_script_rules(
                        rule_key, script_pattern, rule_text, status, videos, events,
                        avg_drop, median_drop, opening_videos, first_seen_at,
                        last_seen_at, activated_at, retired_at, evidence_json
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        key, item["script_pattern"], item["rule_text"], item["status"],
                        item["videos"], item["events"], item["avg_drop"], item["median_drop"],
                        item["opening_videos"], now, now, activated_at, None, item["evidence_json"],
                    ),
                )
                if item["status"] == "ACTIVE":
                    activated += 1
            else:
                became_active = old.get("status") != "ACTIVE" and item["status"] == "ACTIVE"
                activated_at = old.get("activated_at") or (now if became_active else None)
                con.execute(
                    """
                    UPDATE channel_script_rules
                    SET script_pattern=?, rule_text=?, status=?, videos=?, events=?,
                        avg_drop=?, median_drop=?, opening_videos=?, last_seen_at=?,
                        activated_at=?, retired_at=NULL, evidence_json=?
                    WHERE rule_key=?
                    """,
                    (
                        item["script_pattern"], item["rule_text"], item["status"],
                        item["videos"], item["events"], item["avg_drop"], item["median_drop"],
                        item["opening_videos"], now, activated_at, item["evidence_json"], key,
                    ),
                )
                updated += 1
                if became_active:
                    activated += 1

        # Rules absent from the current evidence are not deleted. They become RETIRED.
        for key, old in existing.items():
            if key in current:
                continue
            if old.get("status") != "RETIRED":
                con.execute(
                    """
                    UPDATE channel_script_rules
                    SET status='RETIRED', retired_at=?, last_seen_at=?
                    WHERE rule_key=?
                    """,
                    (now, now, key),
                )
                retired += 1

    active = active_channel_script_rules(db_path)
    return {
        "active": int(len(active)),
        "activated": activated,
        "updated": updated,
        "retired": retired,
        "learning_summary": learned.get("summary") or {},
    }


def render_active_channel_rules_markdown(db_path: Path) -> str:
    """
    Build the exact writer-facing rules block. Medical/evidence/title constraints
    remain higher priority than learned retention rules.
    """
    active = active_channel_script_rules(db_path)
    lines = [
        "# ACTIVE CHANNEL SCRIPT RULES",
        "",
        "These rules were learned automatically from repeated retention-linked script patterns.",
        "Apply them to future scripts unless they conflict with the immutable winning title,",
        "approved research/evidence, Medical Gate requirements, or required safety language.",
        "They guide delivery/structure only; they must never weaken medical accuracy or required cautions.",
        "",
    ]
    if active.empty:
        lines.append("_No ACTIVE channel script rules yet._")
        return "\n".join(lines).strip() + "\n"

    for idx, row in active.iterrows():
        rule = str(row.get("rule_text") or "").strip()
        pattern = str(row.get("script_pattern") or "").strip()
        videos = int(row.get("videos") or 0)
        events = int(row.get("events") or 0)
        avg_drop = row.get("avg_drop")
        evidence = f"{videos} learning-eligible videos / {events} retention events"
        if avg_drop is not None and not pd.isna(avg_drop):
            evidence += f" / avg change {float(avg_drop):.2f} points"
        lines.extend([
            f"## Rule {idx + 1}: {pattern}",
            f"- **Instruction:** {rule}",
            f"- **Evidence:** {evidence}",
            "",
        ])
    return "\n".join(lines).strip() + "\n"


def write_active_channel_rules_file(db_path: Path, output_path: Path) -> dict[str, Any]:
    """Synchronize lifecycle and write the current ACTIVE rules artifact."""
    result = sync_active_channel_script_rules(db_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_active_channel_rules_markdown(db_path),
        encoding="utf-8",
        newline="\n",
    )
    result["path"] = str(output_path)
    return result


def record_thumbnail_analysis(
    db_path: Path, thumbnail_snapshot_id: int, *, analytics_id: str, youtube_video_id: str,
    analyzed_at: str, model: str, title_at_analysis: str, features: dict[str, Any], raw_response: str = "",
) -> int:
    """Persist structured vision features for one immutable thumbnail snapshot."""
    init_db(db_path)
    def b(name: str):
        value = features.get(name)
        return None if value is None else int(bool(value))
    def i(name: str):
        try:
            return int(features.get(name)) if features.get(name) is not None else None
        except (TypeError, ValueError):
            return None
    def f(name: str):
        try:
            return float(features.get(name)) if features.get(name) is not None else None
        except (TypeError, ValueError):
            return None
    def t(name: str):
        value = features.get(name)
        return None if value is None else str(value).strip()
    with _db_connect(db_path) as con:
        snap = con.execute("SELECT analytics_id,youtube_video_id FROM thumbnail_snapshots WHERE id=?", (int(thumbnail_snapshot_id),)).fetchone()
        if not snap:
            raise AnalyticsDBError("Unknown thumbnail snapshot.")
        if str(snap["analytics_id"]) != str(analytics_id) or str(snap["youtube_video_id"]) != str(youtube_video_id):
            raise AnalyticsDBError("Thumbnail analysis identity does not match the archived snapshot.")
        con.execute(
            """INSERT INTO thumbnail_analyses
               (thumbnail_snapshot_id,analytics_id,youtube_video_id,analyzed_at,model,title_at_analysis,
                presenter_present,presenter_position,presenter_size,expression,gaze_target,hero_subject,hero_category,hero_count,
                thumbnail_text,text_word_count,text_line_count,text_style,question_hook,number_hook,arrow_present,arrow_target,
                background_style,background_brightness,background_color_family,dominant_palette,text_color_scheme,accent_color_family,palette_temperature,contrast_level,visual_complexity,major_visual_object_count,composition_layout,subject_separation,
                curiosity_mechanism,title_thumbnail_relationship,semantic_summary,confidence,features_json,raw_response)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(thumbnail_snapshot_id) DO UPDATE SET
                analyzed_at=excluded.analyzed_at,model=excluded.model,title_at_analysis=excluded.title_at_analysis,
                presenter_present=excluded.presenter_present,presenter_position=excluded.presenter_position,presenter_size=excluded.presenter_size,
                expression=excluded.expression,gaze_target=excluded.gaze_target,hero_subject=excluded.hero_subject,hero_category=excluded.hero_category,hero_count=excluded.hero_count,
                thumbnail_text=excluded.thumbnail_text,text_word_count=excluded.text_word_count,text_line_count=excluded.text_line_count,
                text_style=excluded.text_style,question_hook=excluded.question_hook,number_hook=excluded.number_hook,arrow_present=excluded.arrow_present,
                arrow_target=excluded.arrow_target,background_style=excluded.background_style,background_brightness=excluded.background_brightness,
                background_color_family=excluded.background_color_family,dominant_palette=excluded.dominant_palette,text_color_scheme=excluded.text_color_scheme,
                accent_color_family=excluded.accent_color_family,palette_temperature=excluded.palette_temperature,contrast_level=excluded.contrast_level,
                visual_complexity=excluded.visual_complexity,major_visual_object_count=excluded.major_visual_object_count,
                composition_layout=excluded.composition_layout,subject_separation=excluded.subject_separation,
                curiosity_mechanism=excluded.curiosity_mechanism,title_thumbnail_relationship=excluded.title_thumbnail_relationship,
                semantic_summary=excluded.semantic_summary,confidence=excluded.confidence,features_json=excluded.features_json,raw_response=excluded.raw_response""",
            (int(thumbnail_snapshot_id),analytics_id,youtube_video_id,analyzed_at,model,title_at_analysis,
             b("presenter_present"),t("presenter_position"),t("presenter_size"),t("expression"),t("gaze_target"),t("hero_subject"),t("hero_category"),i("hero_count"),
             t("thumbnail_text"),i("text_word_count"),i("text_line_count"),t("text_style"),b("question_hook"),b("number_hook"),b("arrow_present"),t("arrow_target"),
             t("background_style"),t("background_brightness"),t("background_color_family"),t("dominant_palette"),t("text_color_scheme"),t("accent_color_family"),t("palette_temperature"),t("contrast_level"),t("visual_complexity"),i("major_visual_object_count"),t("composition_layout"),t("subject_separation"),
             t("curiosity_mechanism"),t("title_thumbnail_relationship"),t("semantic_summary"),f("confidence"),
             json.dumps(features,ensure_ascii=False,sort_keys=True),raw_response),
        )
        con.execute("UPDATE thumbnail_snapshots SET analysis_status='analyzed' WHERE id=?", (int(thumbnail_snapshot_id),))
        row=con.execute("SELECT id FROM thumbnail_analyses WHERE thumbnail_snapshot_id=?", (int(thumbnail_snapshot_id),)).fetchone()
        con.commit()
        return int(row["id"])


def thumbnail_analysis_df(db_path: Path, analytics_id: str | None = None) -> pd.DataFrame:
    init_db(db_path)
    with _db_connect(db_path) as con:
        sql="""SELECT a.*,s.file_path,s.source_variant,s.downloaded_at,
                      COALESCE(NULLIF(v.youtube_title,''),NULLIF(v.locked_title,''),v.project_slug,v.analytics_id) AS title
               FROM thumbnail_analyses a
               JOIN thumbnail_snapshots s ON s.id=a.thumbnail_snapshot_id
               JOIN videos v ON v.analytics_id=a.analytics_id"""
        params=()
        if analytics_id:
            sql += " WHERE a.analytics_id=?"; params=(analytics_id,)
        sql += " ORDER BY a.analyzed_at DESC,a.id DESC"
        rows=con.execute(sql,params).fetchall()
    return pd.DataFrame([dict(r) for r in rows])



def _thumbnail_evidence_weight(impressions: Any) -> float | None:
    """Deterministic sample-strength weight; Stage 3 does not score visual quality."""
    try:
        imp = float(impressions)
    except (TypeError, ValueError):
        return None
    if imp < 0:
        return None
    # Smoothly increases with sample size and caps at 1.0 at 100k impressions.
    import math
    return round(min(1.0, math.log10(max(1.0, imp) + 1.0) / 5.0), 6)


def join_thumbnail_ctr_evidence(db_path: Path, analytics_id: str) -> dict[str, Any]:
    """Stage 3: join current analyzed thumbnail snapshot to measured CTR/impressions.

    This is evidence assembly only. Historical CTR is never asserted to have been
    generated by the currently archived thumbnail; attribution_status makes that
    caveat queryable for later packaging learning.
    """
    init_db(db_path)
    now = _now()
    with _db_connect(db_path) as con:
        video = con.execute(
            "SELECT analytics_id,youtube_video_id FROM videos WHERE analytics_id=?",
            (analytics_id,),
        ).fetchone()
        if not video or not str(video['youtube_video_id'] or '').strip():
            raise AnalyticsDBError("Stage 3 requires a permanently linked YouTube Video ID.")
        snap = con.execute(
            "SELECT * FROM thumbnail_snapshots WHERE analytics_id=? AND is_current=1 ORDER BY id DESC LIMIT 1",
            (analytics_id,),
        ).fetchone()
        if not snap:
            raise AnalyticsDBError("No archived current thumbnail snapshot. Run Stage 1 first.")
        analysis = con.execute(
            "SELECT * FROM thumbnail_analyses WHERE thumbnail_snapshot_id=? ORDER BY id DESC LIMIT 1",
            (int(snap['id']),),
        ).fetchone()
        if not analysis:
            raise AnalyticsDBError("Current thumbnail snapshot has not been analyzed. Run Stage 2 first.")

        # Prefer a clean FUTURE evidence window: only complete daily Reach rows strictly
        # after the thumbnail snapshot calendar date. Same-day data is excluded because
        # it can contain impressions from before the snapshot was archived.
        snapshot_date = str(snap['downloaded_at'] or '')[:10]
        post_reach = con.execute(
            """SELECT SUM(COALESCE(impressions,0)) impressions,
                      CASE WHEN SUM(COALESCE(impressions,0)) > 0
                           THEN SUM(COALESCE(impressions,0)*COALESCE(ctr_percent,0))/SUM(COALESCE(impressions,0)) END ctr_percent,
                      MIN(report_date) start_date, MAX(report_date) end_date, COUNT(*) days,
                      MAX(imported_at) snapshot_at
               FROM reach_daily
               WHERE analytics_id=? AND report_date>?""",
            (analytics_id, snapshot_date),
        ).fetchone()
        if post_reach and post_reach['impressions'] is not None and float(post_reach['impressions'] or 0) > 0 and post_reach['ctr_percent'] is not None:
            ctr, impressions = float(post_reach['ctr_percent']), float(post_reach['impressions'])
            source = 'reach_daily_post_snapshot'
            metric_at = post_reach['snapshot_at']
            start_date, end_date, days = post_reach['start_date'], post_reach['end_date'], int(post_reach['days'] or 0)
            status = 'post_snapshot_window_observed'
            note = (
                'CTR/impressions use complete daily Reach rows strictly after the archived thumbnail snapshot date; '
                'same-day and earlier historical rows are excluded. This is a substantially cleaner temporal match, '
                'but remains observational because an unrecorded thumbnail change between snapshots cannot be ruled out.'
            )
        else:
            # Backward-compatible historical evidence path. Old videos still remain useful
            # for observation, but are explicitly blocked from ACTIVE rule promotion.
            reach = con.execute(
                """SELECT SUM(COALESCE(impressions,0)) impressions,
                          CASE WHEN SUM(COALESCE(impressions,0)) > 0
                               THEN SUM(COALESCE(impressions,0)*COALESCE(ctr_percent,0))/SUM(COALESCE(impressions,0)) END ctr_percent,
                          MIN(report_date) start_date, MAX(report_date) end_date, COUNT(*) days,
                          MAX(imported_at) snapshot_at
                   FROM reach_daily WHERE analytics_id=?""",
                (analytics_id,),
            ).fetchone()
            if reach and reach['impressions'] is not None and float(reach['impressions'] or 0) > 0 and reach['ctr_percent'] is not None:
                ctr, impressions = float(reach['ctr_percent']), float(reach['impressions'])
                source = 'reach_daily_weighted'
                metric_at, start_date, end_date, days = reach['snapshot_at'], reach['start_date'], reach['end_date'], int(reach['days'] or 0)
            else:
                perf = con.execute(
                    """SELECT imported_at,impressions,ctr_percent,date_range_label
                       FROM performance_snapshots
                       WHERE analytics_id=? AND impressions IS NOT NULL AND ctr_percent IS NOT NULL
                       ORDER BY id DESC LIMIT 1""",
                    (analytics_id,),
                ).fetchone()
                if not perf:
                    raise AnalyticsDBError("No measured CTR + impressions are stored for this video yet.")
                ctr, impressions = float(perf['ctr_percent']), float(perf['impressions'])
                source = 'performance_snapshot'
                metric_at, start_date, end_date, days = perf['imported_at'], None, None, None
            status = 'historical_thumbnail_version_uncertain'
            note = ('Measured CTR/impressions are joined to this archived thumbnail for packaging evidence, '
                    'but the current snapshot does not prove this same thumbnail was live for the full metric period.')
        weight = _thumbnail_evidence_weight(impressions)
        con.execute(
            """INSERT INTO thumbnail_ctr_evidence(
                 thumbnail_snapshot_id,thumbnail_analysis_id,analytics_id,youtube_video_id,joined_at,
                 ctr_percent,impressions,metric_source,metric_snapshot_at,metric_start_date,metric_end_date,
                 metric_days,attribution_status,attribution_note,evidence_weight)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(thumbnail_snapshot_id,thumbnail_analysis_id,metric_source) DO UPDATE SET
                 joined_at=excluded.joined_at,ctr_percent=excluded.ctr_percent,impressions=excluded.impressions,
                 metric_snapshot_at=excluded.metric_snapshot_at,metric_start_date=excluded.metric_start_date,
                 metric_end_date=excluded.metric_end_date,metric_days=excluded.metric_days,
                 attribution_status=excluded.attribution_status,attribution_note=excluded.attribution_note,
                 evidence_weight=excluded.evidence_weight""",
            (int(snap['id']),int(analysis['id']),analytics_id,str(video['youtube_video_id']),now,
             ctr,impressions,source,metric_at,start_date,end_date,days,status,note,weight),
        )
        row = con.execute(
            "SELECT * FROM thumbnail_ctr_evidence WHERE thumbnail_snapshot_id=? AND thumbnail_analysis_id=? AND metric_source=?",
            (int(snap['id']),int(analysis['id']),source),
        ).fetchone()
        con.commit()
        return dict(row)


def join_all_thumbnail_ctr_evidence(db_path: Path) -> dict[str, Any]:
    init_db(db_path)
    with _db_connect(db_path) as con:
        ids=[r['analytics_id'] for r in con.execute(
            """SELECT DISTINCT v.analytics_id FROM videos v
               JOIN thumbnail_snapshots s ON s.analytics_id=v.analytics_id AND s.is_current=1
               JOIN thumbnail_analyses a ON a.thumbnail_snapshot_id=s.id
               WHERE v.youtube_video_id IS NOT NULL AND v.youtube_video_id<>''"""
        ).fetchall()]
    out={'checked':len(ids),'joined':0,'failed':0,'errors':[]}
    for aid in ids:
        try:
            join_thumbnail_ctr_evidence(db_path,aid); out['joined']+=1
        except Exception as exc:
            out['failed']+=1; out['errors'].append(f"{aid}: {exc}")
    return out


def thumbnail_ctr_evidence_df(db_path: Path, analytics_id: str | None = None) -> pd.DataFrame:
    init_db(db_path)
    with _db_connect(db_path) as con:
        sql="""SELECT e.*, a.presenter_present,a.presenter_position,a.presenter_size,a.expression,a.gaze_target,
                      a.hero_subject,a.hero_category,a.hero_count,a.thumbnail_text,a.text_word_count,a.text_line_count,
                      a.question_hook,a.number_hook,a.arrow_present,a.arrow_target,a.background_brightness,
                      a.visual_complexity,a.major_visual_object_count,a.composition_layout,a.subject_separation,
                      a.curiosity_mechanism,a.title_thumbnail_relationship,a.confidence,
                      s.downloaded_at AS thumbnail_downloaded_at,s.sha256 AS thumbnail_sha256,
                      COALESCE(NULLIF(v.youtube_title,''),NULLIF(v.locked_title,''),v.project_slug,v.analytics_id) title
               FROM thumbnail_ctr_evidence e
               JOIN thumbnail_analyses a ON a.id=e.thumbnail_analysis_id
               JOIN thumbnail_snapshots s ON s.id=e.thumbnail_snapshot_id
               JOIN videos v ON v.analytics_id=e.analytics_id"""
        params=()
        if analytics_id:
            sql += " WHERE e.analytics_id=?"; params=(analytics_id,)
        sql += " ORDER BY e.joined_at DESC,e.id DESC"
        rows=con.execute(sql,params).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


# ---------------- CTR / Packaging Learning: Stage 4 ----------------

_STAGE4_PACKAGING_FEATURES = (
    "presenter_present", "presenter_position", "presenter_size", "expression",
    "gaze_target", "hero_subject", "hero_count", "text_word_count",
    "text_length_bucket", "text_line_count", "text_density_bucket", "question_hook", "number_hook", "arrow_present",
    "arrow_target", "background_style", "background_brightness",
    "background_color_family", "dominant_palette", "text_color_scheme", "accent_color_family",
    "palette_temperature", "contrast_level", "visual_complexity", "major_visual_object_count", "composition_layout",
    "subject_separation", "curiosity_mechanism", "title_thumbnail_relationship",
)


def _stage4_feature_value(value: Any) -> str | None:
    """Normalize a visually extracted feature for cross-video comparison."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        # SQLite booleans arrive as 0/1 for known binary fields; callers keep
        # exact count values for count features.
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return str(value)
    text = str(value).strip()
    if not text or text.lower() in {"unknown", "null", "none", "n/a", "na"}:
        return None
    return text


def _stage4_maturity(video_count: int) -> str:
    if int(video_count) >= 3:
        return "CHANNEL PATTERN CANDIDATE"
    if int(video_count) == 2:
        return "REPEATED SIGNAL"
    return "OBSERVATION"


def _stage4_weighted_ctr(rows: list[dict[str, Any]]) -> tuple[float | None, float]:
    valid = []
    for row in rows:
        try:
            imp = float(row.get("impressions"))
            ctr = float(row.get("ctr_percent"))
        except (TypeError, ValueError):
            continue
        if imp > 0:
            valid.append((imp, ctr))
    total = sum(imp for imp, _ in valid)
    if total <= 0:
        return None, 0.0
    return sum(imp * ctr for imp, ctr in valid) / total, total


def _latest_thumbnail_packaging_evidence(db_path: Path) -> list[dict[str, Any]]:
    """Return one latest Stage-3 evidence row per video, preventing duplicate re-analysis weighting."""
    init_db(db_path)
    with _db_connect(db_path) as con:
        rows = con.execute(
            """SELECT e.*,
                      a.presenter_present,a.presenter_position,a.presenter_size,a.expression,a.gaze_target,
                      a.hero_subject,a.hero_category,a.hero_count,a.thumbnail_text,a.text_word_count,a.text_line_count,a.text_style,
                      a.question_hook,a.number_hook,a.arrow_present,a.arrow_target,a.background_style,
                      a.background_brightness,a.background_color_family,a.dominant_palette,a.text_color_scheme,a.accent_color_family,
                      a.palette_temperature,a.contrast_level,a.visual_complexity,a.major_visual_object_count,
                      a.composition_layout,a.subject_separation,a.curiosity_mechanism,a.title_thumbnail_relationship,
                      COALESCE(NULLIF(v.youtube_title,''),NULLIF(v.locked_title,''),v.project_slug,v.analytics_id) title
               FROM thumbnail_ctr_evidence e
               JOIN thumbnail_analyses a ON a.id=e.thumbnail_analysis_id
               JOIN videos v ON v.analytics_id=e.analytics_id
               WHERE e.id=(
                   SELECT e2.id FROM thumbnail_ctr_evidence e2
                   WHERE e2.analytics_id=e.analytics_id
                   ORDER BY e2.joined_at DESC,e2.id DESC LIMIT 1
               )
                 AND e.ctr_percent IS NOT NULL AND e.impressions IS NOT NULL AND e.impressions > 0
               ORDER BY e.analytics_id"""
        ).fetchall()
    out = [dict(r) for r in rows]
    # Deterministic thumbnail-copy features. These are derived from the exact
    # visible-text counts already stored by Stage 2, so existing analyzed
    # thumbnails gain text-length learning without another vision/API pass.
    _derive_thumbnail_text_pattern_features(out)
    return out


def build_thumbnail_packaging_comparisons(db_path: Path) -> dict[str, Any]:
    """Stage 4: build contextual, impression-aware cross-video packaging associations.

    This stage is descriptive evidence only. It does not promote ACTIVE rules and
    never treats a visual feature as causal. Comparisons are made channel-wide and,
    where visually available, within the same hero_category context.
    """
    init_db(db_path)
    evidence = _latest_thumbnail_packaging_evidence(db_path)
    if len(evidence) < 2:
        raise AnalyticsDBError("Stage 4 needs CTR evidence for at least 2 different videos before cross-video comparison.")

    contexts: list[tuple[str, str, list[dict[str, Any]]]] = [("channel", "all", evidence)]
    by_hero: dict[str, list[dict[str, Any]]] = {}
    for row in evidence:
        ctx = _stage4_feature_value(row.get("hero_category"))
        if ctx:
            by_hero.setdefault(ctx, []).append(row)
    for ctx, rows in sorted(by_hero.items()):
        if len({r["analytics_id"] for r in rows}) >= 2:
            contexts.append(("hero_category", ctx, rows))

    now = _now()
    associations: list[dict[str, Any]] = []
    for context_type, context_value, ctx_rows in contexts:
        for feature in _STAGE4_PACKAGING_FEATURES:
            grouped: dict[str, list[dict[str, Any]]] = {}
            for row in ctx_rows:
                val = _stage4_feature_value(row.get(feature))
                if val is not None:
                    grouped.setdefault(val, []).append(row)
            if len(grouped) < 2:
                continue
            for value, group_rows in sorted(grouped.items()):
                group_ids = {r["analytics_id"] for r in group_rows}
                comparison_rows = [r for r in ctx_rows if r["analytics_id"] not in group_ids and _stage4_feature_value(r.get(feature)) is not None]
                if not comparison_rows:
                    continue
                ctr, impressions = _stage4_weighted_ctr(group_rows)
                comp_ctr, comp_impressions = _stage4_weighted_ctr(comparison_rows)
                if ctr is None or comp_ctr is None:
                    continue
                delta = ctr - comp_ctr
                if delta > 0.25:
                    direction = "stronger_ctr_association"
                    phrase = "stronger"
                elif delta < -0.25:
                    direction = "weaker_ctr_association"
                    phrase = "weaker"
                else:
                    direction = "similar_ctr_association"
                    phrase = "similar"
                vc = len(group_ids)
                maturity = _stage4_maturity(vc)
                weight = _thumbnail_evidence_weight(impressions)
                group_attr_statuses = sorted({str(r.get("attribution_status") or "unknown") for r in group_rows})
                comparison_attr_statuses = sorted({str(r.get("attribution_status") or "unknown") for r in comparison_rows})
                all_attr_statuses = sorted(set(group_attr_statuses + comparison_attr_statuses))
                attribution_status = all_attr_statuses[0] if len(all_attr_statuses) == 1 else "mixed_attribution_caveats"
                context_label = "channel-wide" if context_type == "channel" else f"hero category '{context_value}'"
                interpretation = (
                    f"Within {context_label}, {feature}={value!r} was associated with {phrase} measured CTR "
                    f"than other observed values ({ctr:.2f}% vs {comp_ctr:.2f}%; delta {delta:+.2f} points) "
                    f"across {vc} video(s). This is correlational packaging evidence, not a causal rule."
                )
                associations.append({
                    "computed_at": now, "context_type": context_type, "context_value": context_value,
                    "feature_name": feature, "feature_value": value, "video_count": vc,
                    "total_impressions": impressions, "weighted_ctr": ctr,
                    "comparison_video_count": len({r["analytics_id"] for r in comparison_rows}),
                    "comparison_impressions": comp_impressions, "comparison_weighted_ctr": comp_ctr,
                    "ctr_delta_points": delta, "evidence_weight": weight, "maturity": maturity,
                    "association_direction": direction, "attribution_status": attribution_status,
                    "interpretation": interpretation,
                    "evidence_json": json.dumps({
                        "analytics_ids": sorted(group_ids),
                        "comparison_analytics_ids": sorted({r["analytics_id"] for r in comparison_rows}),
                        "metric_sources": sorted({str(r.get("metric_source") or "") for r in group_rows}),
                        "group_attribution_statuses": group_attr_statuses,
                        "comparison_attribution_statuses": comparison_attr_statuses,
                        "attribution_statuses": all_attr_statuses,
                    }, ensure_ascii=False, sort_keys=True),
                })

    with _db_connect(db_path) as con:
        cur = con.execute(
            "INSERT INTO thumbnail_packaging_comparison_runs(computed_at,evidence_video_count,association_count,notes) VALUES(?,?,?,?)",
            (now, len({r['analytics_id'] for r in evidence}), len(associations),
             "Stage 4 contextual association run; no ACTIVE packaging rules are promoted."),
        )
        run_id = int(cur.lastrowid)
        for a in associations:
            con.execute(
                """INSERT INTO thumbnail_packaging_associations(
                     run_id,computed_at,context_type,context_value,feature_name,feature_value,video_count,
                     total_impressions,weighted_ctr,comparison_video_count,comparison_impressions,
                     comparison_weighted_ctr,ctr_delta_points,evidence_weight,maturity,association_direction,
                     attribution_status,interpretation,evidence_json)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (run_id,a['computed_at'],a['context_type'],a['context_value'],a['feature_name'],a['feature_value'],
                 a['video_count'],a['total_impressions'],a['weighted_ctr'],a['comparison_video_count'],
                 a['comparison_impressions'],a['comparison_weighted_ctr'],a['ctr_delta_points'],a['evidence_weight'],
                 a['maturity'],a['association_direction'],a['attribution_status'],a['interpretation'],a['evidence_json']),
            )
        con.commit()
    return {"run_id": run_id, "computed_at": now, "evidence_videos": len({r['analytics_id'] for r in evidence}),
            "contexts": len(contexts), "associations": len(associations)}


def thumbnail_packaging_associations_df(db_path: Path, run_id: int | None = None) -> pd.DataFrame:
    """Return Stage-4 associations, defaulting to the latest comparison run."""
    init_db(db_path)
    with _db_connect(db_path) as con:
        if run_id is None:
            row = con.execute("SELECT id FROM thumbnail_packaging_comparison_runs ORDER BY id DESC LIMIT 1").fetchone()
            if not row:
                return pd.DataFrame()
            run_id = int(row['id'])
        rows = con.execute(
            """SELECT * FROM thumbnail_packaging_associations
               WHERE run_id=?
               ORDER BY CASE maturity WHEN 'CHANNEL PATTERN CANDIDATE' THEN 1 WHEN 'REPEATED SIGNAL' THEN 2 ELSE 3 END,
                        ABS(COALESCE(ctr_delta_points,0)) DESC,total_impressions DESC,id""",
            (int(run_id),),
        ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])



PACKAGING_PROMOTION_MIN_VIDEOS_PER_COHORT = 3
PACKAGING_PROMOTION_MIN_IMPRESSIONS_PER_COHORT = 1000.0


def _two_proportion_delta_ci(ctr_a: float, impressions_a: float, ctr_b: float, impressions_b: float) -> tuple[float, float, float]:
    """Approximate 95% CI for CTR percentage-point difference using impression counts.

    CTR is already an aggregate YouTube metric, so this is a screening diagnostic,
    not causal/statistical proof. It prevents promotion when the observed difference
    is too noisy to distinguish from zero at the available impression volume.
    """
    import math
    n1=max(float(impressions_a),1.0); n2=max(float(impressions_b),1.0)
    p1=max(0.0,min(1.0,float(ctr_a)/100.0)); p2=max(0.0,min(1.0,float(ctr_b)/100.0))
    diff=(p1-p2)*100.0
    se=math.sqrt((p1*(1-p1)/n1)+(p2*(1-p2)/n2))*100.0
    return diff, diff-1.96*se, diff+1.96*se


def packaging_rule_promotion_audit(db_path: Path, rule_key: str) -> dict[str, Any]:
    """Return the Stage-5 manual-review gate with explicit two-sided cohort support."""
    init_db(db_path)
    with _db_connect(db_path) as con:
        rule=con.execute("SELECT * FROM channel_packaging_rules WHERE rule_key=?",(rule_key,)).fetchone()
        if not rule:
            raise AnalyticsDBError("Packaging rule not found.")
        assoc=con.execute("SELECT * FROM thumbnail_packaging_associations WHERE id=?",(rule['source_association_id'],)).fetchone()
    if not assoc:
        return {'promotion_ready':False,'reasons':['Stage 4 source association is missing.']}
    a=dict(assoc); reasons=[]
    group_v=int(a.get('video_count') or 0); comp_v=int(a.get('comparison_video_count') or 0)
    group_imp=float(a.get('total_impressions') or 0); comp_imp=float(a.get('comparison_impressions') or 0)
    attr=str(a.get('attribution_status') or '').strip().lower()
    if attr!='post_snapshot_window_observed':
        reasons.append('Both cohorts must use clean post-snapshot CTR/impressions windows.')
    if group_v < PACKAGING_PROMOTION_MIN_VIDEOS_PER_COHORT or comp_v < PACKAGING_PROMOTION_MIN_VIDEOS_PER_COHORT:
        reasons.append(f'Both cohorts need at least {PACKAGING_PROMOTION_MIN_VIDEOS_PER_COHORT} different videos.')
    if group_imp < PACKAGING_PROMOTION_MIN_IMPRESSIONS_PER_COHORT or comp_imp < PACKAGING_PROMOTION_MIN_IMPRESSIONS_PER_COHORT:
        reasons.append(f'Both cohorts need at least {PACKAGING_PROMOTION_MIN_IMPRESSIONS_PER_COHORT:,.0f} impressions.')
    ci_low=ci_high=None
    if a.get('weighted_ctr') is not None and a.get('comparison_weighted_ctr') is not None and group_imp>0 and comp_imp>0:
        _,ci_low,ci_high=_two_proportion_delta_ci(a['weighted_ctr'],group_imp,a['comparison_weighted_ctr'],comp_imp)
        if ci_low <= 0.0 <= ci_high:
            reasons.append('The approximate 95% CTR-delta interval still crosses zero; keep collecting evidence.')
    else:
        reasons.append('Both cohorts need measured CTR values.')
    return {
        'promotion_ready':not reasons,'reasons':reasons,'attribution_status':a.get('attribution_status'),
        'feature_videos':group_v,'comparison_videos':comp_v,'feature_impressions':group_imp,
        'comparison_impressions':comp_imp,'feature_ctr':a.get('weighted_ctr'),'comparison_ctr':a.get('comparison_weighted_ctr'),
        'ctr_delta_points':a.get('ctr_delta_points'),'delta_ci95_low':ci_low,'delta_ci95_high':ci_high,
        'source_association_id':a.get('id')
    }

# ---------------- CTR / Packaging Learning: Stage 5 ----------------

def _packaging_rule_key(context_type: str, context_value: str, feature_name: str, feature_value: str, direction: str) -> str:
    raw = "|".join(str(x or "").strip().lower() for x in (context_type, context_value, feature_name, feature_value, direction))
    return re.sub(r"[^a-z0-9]+", "_", raw).strip("_") or "unnamed_packaging_rule"


def _packaging_guidance(row: dict[str, Any]) -> str:
    context = "channel-wide packaging" if row["context_type"] == "channel" else f"{row['context_value']} hero-category packaging"
    feature = str(row["feature_name"]).replace("_", " ")
    value = str(row["feature_value"])
    direction = str(row["association_direction"])
    if direction == "stronger_ctr_association":
        action = f"Prefer testing {feature}={value!r} when it fits the title, evidence, and creative constraints"
    else:
        action = f"Avoid defaulting to {feature}={value!r}; test alternatives when the concept allows"
    return f"{action} in {context}. Treat this as channel evidence associated with CTR, not a causal guarantee."


def sync_packaging_rule_candidates(db_path: Path) -> dict[str, Any]:
    """Stage 5: sync promotable Stage-4 findings into a reviewable lifecycle.

    Only 3+ video CHANNEL PATTERN CANDIDATE findings with a directional CTR
    association become CANDIDATE. Nothing is auto-activated. Existing ACTIVE
    decisions are preserved until explicitly retired by the user.
    """
    init_db(db_path)
    with _db_connect(db_path) as con:
        run = con.execute("SELECT id FROM thumbnail_packaging_comparison_runs ORDER BY id DESC LIMIT 1").fetchone()
        if not run:
            raise AnalyticsDBError("Stage 5 needs a Stage 4 comparison run first.")
        run_id = int(run["id"])
        rows = con.execute(
            """SELECT * FROM thumbnail_packaging_associations
               WHERE run_id=? AND maturity='CHANNEL PATTERN CANDIDATE'
                 AND association_direction IN ('stronger_ctr_association','weaker_ctr_association')
                 AND video_count>=3
               ORDER BY total_impressions DESC,ABS(COALESCE(ctr_delta_points,0)) DESC,id""", (run_id,)
        ).fetchall()
        # A two-value feature produces reciprocal rows (A stronger than B / B weaker than A).
        # They are one comparison, not two independent discoveries. Keep the stronger side as
        # the canonical review candidate; multi-value features remain independently reviewable.
        by_feature={}
        for rr in rows:
            k=(rr['context_type'],rr['context_value'],rr['feature_name'])
            by_feature.setdefault(k,[]).append(rr)
        filtered=[]
        for vals in by_feature.values():
            if len(vals)==2 and {str(x['association_direction']) for x in vals}=={'stronger_ctr_association','weaker_ctr_association'}:
                filtered.append(next(x for x in vals if str(x['association_direction'])=='stronger_ctr_association'))
            else:
                filtered.extend(vals)
        rows=filtered
        now=_now(); seen=set(); created=updated=0
        for rr in rows:
            r=dict(rr)
            key=_packaging_rule_key(r['context_type'],r['context_value'],r['feature_name'],r['feature_value'],r['association_direction'])
            seen.add(key)
            old=con.execute("SELECT * FROM channel_packaging_rules WHERE rule_key=?",(key,)).fetchone()
            status = str(old['status']) if old and str(old['status']) in {'ACTIVE','REJECTED','RETIRED'} else 'CANDIDATE'
            evidence=json.dumps({
                'stage4_run_id':run_id,'association_id':r['id'],'video_count':r['video_count'],
                'total_impressions':r['total_impressions'],'weighted_ctr':r['weighted_ctr'],
                'comparison_weighted_ctr':r['comparison_weighted_ctr'],'ctr_delta_points':r['ctr_delta_points'],
                'association_direction':r['association_direction'],'attribution_status':r['attribution_status'],
                'stage4_interpretation':r['interpretation']
            },ensure_ascii=False,sort_keys=True)
            vals=(r['context_type'],r['context_value'],r['feature_name'],r['feature_value'],r['association_direction'],
                  _packaging_guidance(r),status,run_id,r['id'],r['video_count'],r['total_impressions'],r['weighted_ctr'],
                  r['comparison_weighted_ctr'],r['ctr_delta_points'],r['evidence_weight'],r['attribution_status'],now,evidence,key)
            if old:
                con.execute("""UPDATE channel_packaging_rules SET context_type=?,context_value=?,feature_name=?,feature_value=?,direction=?,
                    guidance_text=?,status=?,source_run_id=?,source_association_id=?,videos=?,total_impressions=?,weighted_ctr=?,
                    comparison_weighted_ctr=?,ctr_delta_points=?,evidence_weight=?,attribution_status=?,last_seen_at=?,evidence_json=?
                    WHERE rule_key=?""",vals); updated+=1
            else:
                con.execute("""INSERT INTO channel_packaging_rules(rule_key,context_type,context_value,feature_name,feature_value,direction,
                    guidance_text,status,source_run_id,source_association_id,videos,total_impressions,weighted_ctr,comparison_weighted_ctr,
                    ctr_delta_points,evidence_weight,attribution_status,first_seen_at,last_seen_at,evidence_json)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(key,r['context_type'],r['context_value'],r['feature_name'],r['feature_value'],r['association_direction'],
                    _packaging_guidance(r),status,run_id,r['id'],r['video_count'],r['total_impressions'],r['weighted_ctr'],
                    r['comparison_weighted_ctr'],r['ctr_delta_points'],r['evidence_weight'],r['attribution_status'],now,now,evidence)); created+=1
        con.commit()
    return {'run_id':run_id,'eligible_associations':len(rows),'created':created,'updated':updated,'active':len(active_channel_packaging_rules(db_path))}


def promote_packaging_signal_cluster(
    db_path: Path,
    cluster_name: str,
    representative_rule_key: str,
    supporting_rule_keys: list[str] | tuple[str, ...] | None = None,
    review_note: str = "",
) -> dict[str, Any]:
    """Promote one correlated packaging cluster as a single ACTIVE guidance rule.

    The representative raw rule must independently pass the existing Stage-5
    promotion gate. Supporting rules are recorded as correlated context only;
    their CTR deltas are never summed and they are not treated as independent
    proof. The synthetic ACTIVE row survives future candidate refreshes because
    it uses a dedicated ``signal_cluster`` feature name.
    """
    init_db(db_path)
    cluster_name = str(cluster_name or "").strip()
    if not cluster_name:
        raise AnalyticsDBError("Cluster name is required.")
    supporting_rule_keys = [str(x) for x in (supporting_rule_keys or []) if str(x).strip()]
    audit = packaging_rule_promotion_audit(db_path, representative_rule_key)
    if not audit.get('promotion_ready'):
        raise AnalyticsDBError("Cannot promote cluster to ACTIVE: " + " ".join(audit.get('reasons') or []))

    now = _now()
    with _db_connect(db_path) as con:
        rep = con.execute("SELECT * FROM channel_packaging_rules WHERE rule_key=?", (representative_rule_key,)).fetchone()
        if not rep:
            raise AnalyticsDBError("Representative packaging rule not found.")
        rep = dict(rep)
        support_rows = []
        for key in supporting_rule_keys:
            row = con.execute("SELECT * FROM channel_packaging_rules WHERE rule_key=?", (key,)).fetchone()
            if not row:
                continue
            d = dict(row)
            # A cluster must stay within the same learned context and direction.
            if d.get('context_type') != rep.get('context_type') or d.get('context_value') != rep.get('context_value'):
                continue
            if d.get('direction') != rep.get('direction'):
                continue
            support_rows.append(d)

        examples = [f"{r['feature_name']}={r['feature_value']}" for r in support_rows]
        rep_example = f"{rep['feature_name']}={rep['feature_value']}"
        direction = str(rep.get('direction') or '')
        if direction == 'stronger_ctr_association':
            action = f'Prefer testing the broader "{cluster_name}" packaging pattern when it fits the project'
        else:
            action = f'Avoid defaulting to the broader "{cluster_name}" packaging pattern; test alternatives when the project allows'
        guidance = (
            f"{action}. Representative channel signal: {rep_example}. "
            + (f"Correlated supporting signals: {', '.join(examples[:6])}. " if examples else "")
            + "Treat these measurements as one correlated pattern, not separate wins; do not force every micro-feature simultaneously. "
              "Preserve senior clarity, title promise, evidence, medical safety, mobile readability, and project-specific creative fit. "
              "This is observational CTR association, not a causal guarantee."
        )
        cluster_feature = 'signal_cluster'
        cluster_value = cluster_name
        key = _packaging_rule_key(rep['context_type'], rep['context_value'], cluster_feature, cluster_value, direction)
        evidence = json.dumps({
            'cluster_name': cluster_name,
            'representative_rule_key': representative_rule_key,
            'representative_signal': rep_example,
            'supporting_rule_keys': [r['rule_key'] for r in support_rows],
            'supporting_signals': examples,
            'note': 'Correlated evidence cluster; CTR deltas are not added together.',
            'representative_audit': audit,
        }, ensure_ascii=False, sort_keys=True)
        old = con.execute("SELECT * FROM channel_packaging_rules WHERE rule_key=?", (key,)).fetchone()
        activated_at = (old['activated_at'] if old else None) or now
        common = (
            rep['context_type'], rep['context_value'], cluster_feature, cluster_value, direction,
            guidance, 'ACTIVE', rep.get('source_run_id'), rep.get('source_association_id'),
            int(rep.get('videos') or 0), float(rep.get('total_impressions') or 0), rep.get('weighted_ctr'),
            rep.get('comparison_weighted_ctr'), rep.get('ctr_delta_points'), rep.get('evidence_weight'),
            rep.get('attribution_status'), now, activated_at, now, str(review_note or ''), evidence,
        )
        if old:
            con.execute("""UPDATE channel_packaging_rules SET context_type=?,context_value=?,feature_name=?,feature_value=?,direction=?,
                guidance_text=?,status=?,source_run_id=?,source_association_id=?,videos=?,total_impressions=?,weighted_ctr=?,
                comparison_weighted_ctr=?,ctr_delta_points=?,evidence_weight=?,attribution_status=?,last_seen_at=?,activated_at=?,
                reviewed_at=?,review_note=?,evidence_json=?,retired_at=NULL WHERE rule_key=?""", common + (key,))
        else:
            con.execute("""INSERT INTO channel_packaging_rules(rule_key,context_type,context_value,feature_name,feature_value,direction,
                guidance_text,status,source_run_id,source_association_id,videos,total_impressions,weighted_ctr,comparison_weighted_ctr,
                ctr_delta_points,evidence_weight,attribution_status,first_seen_at,last_seen_at,activated_at,reviewed_at,review_note,evidence_json)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (key, rep['context_type'], rep['context_value'], cluster_feature, cluster_value, direction, guidance, 'ACTIVE',
                 rep.get('source_run_id'), rep.get('source_association_id'), int(rep.get('videos') or 0),
                 float(rep.get('total_impressions') or 0), rep.get('weighted_ctr'), rep.get('comparison_weighted_ctr'),
                 rep.get('ctr_delta_points'), rep.get('evidence_weight'), rep.get('attribution_status'), now, now,
                 activated_at, now, str(review_note or ''), evidence))
        con.commit()
    return {'rule_key': key, 'status': 'ACTIVE', 'cluster_name': cluster_name, 'representative_rule_key': representative_rule_key}


def set_packaging_rule_status(db_path: Path, rule_key: str, status: str, review_note: str = "") -> dict[str, Any]:
    allowed={'CANDIDATE','ACTIVE','REJECTED','RETIRED'}
    status=str(status).upper().strip()
    if status not in allowed: raise AnalyticsDBError(f"Invalid packaging rule status: {status}")
    init_db(db_path); now=_now()
    with _db_connect(db_path) as con:
        row=con.execute("SELECT * FROM channel_packaging_rules WHERE rule_key=?",(rule_key,)).fetchone()
        if not row: raise AnalyticsDBError("Packaging rule not found.")
        if status == 'ACTIVE':
            audit=packaging_rule_promotion_audit(db_path,rule_key)
            if not audit['promotion_ready']:
                raise AnalyticsDBError("Cannot promote to ACTIVE: " + " ".join(audit['reasons']))
        activated = row['activated_at'] or (now if status=='ACTIVE' else None)
        retired = now if status=='RETIRED' else None
        con.execute("UPDATE channel_packaging_rules SET status=?,reviewed_at=?,review_note=?,activated_at=?,retired_at=? WHERE rule_key=?",
                    (status,now,str(review_note or ''),activated,retired,rule_key)); con.commit()
    return {'rule_key':rule_key,'status':status}


def all_channel_packaging_rules(db_path: Path) -> pd.DataFrame:
    init_db(db_path)
    with _db_connect(db_path) as con:
        rows=con.execute("""SELECT * FROM channel_packaging_rules ORDER BY
          CASE status WHEN 'ACTIVE' THEN 1 WHEN 'CANDIDATE' THEN 2 WHEN 'REJECTED' THEN 3 WHEN 'RETIRED' THEN 4 ELSE 5 END,
          videos DESC,total_impressions DESC,ABS(COALESCE(ctr_delta_points,0)) DESC""").fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def active_channel_packaging_rules(db_path: Path) -> pd.DataFrame:
    df=all_channel_packaging_rules(db_path)
    return df[df['status']=='ACTIVE'].reset_index(drop=True) if not df.empty else df


def _thumbnail_pattern_example_rows(db_path: Path) -> list[dict[str, Any]]:
    """Measured historical thumbnail rows available as ACTIVE-pattern exemplars.

    Unlike Stage 4 scoring, exemplar retrieval intentionally keeps historical
    thumbnail versions. This lets an ACTIVE rule continue to expose the real
    thumbnail version that produced the learned signal even if the video's current
    thumbnail later changes. One latest CTR evidence row is retained per analyzed
    thumbnail version to avoid duplicate evidence-window copies.
    """
    init_db(db_path)
    with _db_connect(db_path) as con:
        rows = con.execute(
            """SELECT e.*,
                      a.presenter_present,a.presenter_position,a.presenter_size,a.expression,a.gaze_target,
                      a.hero_subject,a.hero_category,a.hero_count,a.thumbnail_text,a.text_word_count,a.text_line_count,a.text_style,
                      a.question_hook,a.number_hook,a.arrow_present,a.arrow_target,a.background_style,
                      a.background_brightness,a.background_color_family,a.dominant_palette,a.text_color_scheme,a.accent_color_family,
                      a.palette_temperature,a.contrast_level,a.visual_complexity,a.major_visual_object_count,
                      a.composition_layout,a.subject_separation,a.curiosity_mechanism,a.title_thumbnail_relationship,
                      s.file_path AS thumbnail_file_path,s.downloaded_at AS thumbnail_captured_at,
                      COALESCE(NULLIF(v.youtube_title,''),NULLIF(v.locked_title,''),v.project_slug,v.analytics_id) title
               FROM thumbnail_ctr_evidence e
               JOIN thumbnail_analyses a ON a.id=e.thumbnail_analysis_id
               JOIN thumbnail_snapshots s ON s.id=e.thumbnail_snapshot_id
               JOIN videos v ON v.analytics_id=e.analytics_id
               WHERE e.id=(
                   SELECT e2.id FROM thumbnail_ctr_evidence e2
                   WHERE e2.thumbnail_analysis_id=e.thumbnail_analysis_id
                   ORDER BY e2.joined_at DESC,e2.id DESC LIMIT 1
               )
                 AND e.ctr_percent IS NOT NULL AND e.impressions IS NOT NULL AND e.impressions > 0
               ORDER BY e.joined_at DESC,e.id DESC"""
        ).fetchall()
    out = [dict(r) for r in rows]
    _derive_thumbnail_text_pattern_features(out)
    return out


def _derive_thumbnail_text_pattern_features(rows: list[dict[str, Any]]) -> None:
    """Attach deterministic text-length/density buckets in-place."""
    for row in rows:
        wc = row.get("text_word_count")
        lc = row.get("text_line_count")
        try:
            wc = int(wc) if wc is not None else None
        except (TypeError, ValueError):
            wc = None
        try:
            lc = int(lc) if lc is not None else None
        except (TypeError, ValueError):
            lc = None
        if wc is None:
            row["text_length_bucket"] = None
        elif wc == 0:
            row["text_length_bucket"] = "0 words"
        elif wc <= 3:
            row["text_length_bucket"] = "1-3 words"
        elif wc <= 5:
            row["text_length_bucket"] = "4-5 words"
        elif wc <= 7:
            row["text_length_bucket"] = "6-7 words"
        elif wc <= 10:
            row["text_length_bucket"] = "8-10 words"
        else:
            row["text_length_bucket"] = "11+ words"
        if wc is None or lc is None or lc <= 0:
            row["text_density_bucket"] = None
        else:
            words_per_line = wc / lc
            if words_per_line <= 2.0:
                row["text_density_bucket"] = "<=2 words/line"
            elif words_per_line <= 4.0:
                row["text_density_bucket"] = ">2-4 words/line"
            else:
                row["text_density_bucket"] = ">4 words/line"


def _rule_source_analytics_ids(db_path: Path, rule: dict[str, Any]) -> set[str]:
    """Return the original Stage-4 feature cohort behind an ACTIVE rule when available."""
    association_id = rule.get('source_association_id')
    if association_id in (None, ''):
        return set()
    try:
        association_id = int(association_id)
    except (TypeError, ValueError):
        return set()
    init_db(db_path)
    with _db_connect(db_path) as con:
        row = con.execute(
            "SELECT evidence_json FROM thumbnail_packaging_associations WHERE id=?",
            (association_id,),
        ).fetchone()
    if not row:
        return set()
    try:
        payload = json.loads(str(row['evidence_json'] or '{}'))
    except Exception:
        return set()
    return {str(x) for x in (payload.get('analytics_ids') or []) if str(x).strip()}

def _pattern_feature_value(row: dict[str, Any], feature_name: str) -> str | None:
    value = row.get(feature_name)
    return _stage4_feature_value(value)


def _active_rule_signals(rule: dict[str, Any]) -> list[tuple[str, str]]:
    """Return representative/supporting micro-signals stored behind an ACTIVE rule."""
    if str(rule.get('feature_name') or '') != 'signal_cluster':
        name = str(rule.get('feature_name') or '').strip()
        value = str(rule.get('feature_value') or '').strip()
        return [(name, value)] if name and value else []
    try:
        evidence = json.loads(str(rule.get('evidence_json') or '{}'))
    except Exception:
        evidence = {}
    raw = []
    rep = str(evidence.get('representative_signal') or '').strip()
    if rep:
        raw.append(rep)
    raw.extend(str(x).strip() for x in (evidence.get('supporting_signals') or []) if str(x).strip())
    out = []
    for item in raw:
        if '=' not in item:
            continue
        name, value = item.split('=', 1)
        name, value = name.strip(), value.strip()
        if name and value and (name, value) not in out:
            out.append((name, value))
    return out


def _rule_pattern_examples(db_path: Path, rule: dict[str, Any], limit: int = 6) -> list[dict[str, Any]]:
    """Select real matching channel thumbnails for a promoted rule/cluster.

    Matching is context-first, then by the representative/supporting signals. For
    clusters, a historical thumbnail may match any correlated signal; rows matching
    more signals rank higher. Impressions break ties so tiny samples do not dominate.
    """
    rows = _thumbnail_pattern_example_rows(db_path)
    context_type = str(rule.get('context_type') or '')
    context_value = str(rule.get('context_value') or '')
    signals = _active_rule_signals(rule)
    source_ids = _rule_source_analytics_ids(db_path, rule)
    candidates = []
    for row in rows:
        if context_type == 'hero_category' and _stage4_feature_value(row.get('hero_category')) != context_value:
            continue
        score = 0
        for name, expected in signals:
            actual = _pattern_feature_value(row, name)
            if actual == expected:
                score += 1
        # Only expose thumbnails that visibly match the promoted signal. Historical
        # versions are retained above, so a later thumbnail replacement does not
        # erase the source pattern from the agent's reference set.
        if signals and score <= 0:
            continue
        d = dict(row)
        d['_pattern_match_count'] = score
        d['_source_cohort_match'] = 1 if str(row.get('analytics_id') or '') in source_ids else 0
        candidates.append(d)
    def key(r):
        try: imp = float(r.get('impressions') or 0)
        except Exception: imp = 0.0
        try: ctr = float(r.get('ctr_percent') or 0)
        except Exception: ctr = 0.0
        return (int(r.get('_source_cohort_match') or 0), int(r.get('_pattern_match_count') or 0), imp, ctr)
    candidates.sort(key=key, reverse=True)
    return candidates[:max(1, int(limit))]


def _compact_pattern_traits(row: dict[str, Any]) -> str:
    pairs = [
        ('presenter', 'presenter_position'), ('presenter_size', 'presenter_size'),
        ('hero', 'hero_category'), ('hero_count', 'hero_count'),
        ('layout', 'composition_layout'), ('objects', 'major_visual_object_count'),
        ('background', 'background_brightness'), ('palette', 'dominant_palette'),
        ('text_colors', 'text_color_scheme'), ('accent', 'accent_color_family'),
        ('contrast', 'contrast_level'), ('lines', 'text_line_count'),
        ('words', 'text_word_count'),
    ]
    out=[]
    for label, key in pairs:
        value=row.get(key)
        if value is None or str(value).strip() in {'', 'None', 'nan'}:
            continue
        out.append(f"{label}={str(value).strip()}")
    return '; '.join(out)


def render_active_packaging_rules_markdown(db_path: Path) -> str:
    active=active_channel_packaging_rules(db_path)
    lines=['# ACTIVE CHANNEL PACKAGING RULES','',
      'These rules were explicitly promoted from repeated, impression-aware CTR associations.',
      'They are channel guidance, not causal guarantees. Creative fit, title promise, evidence, medical safety,',
      'and the immutable Anchor/Outlier Title remain higher-priority constraints.','',
      '## CHANNEL-PATTERN-FIRST GENERATION LOCK','',
      'When an ACTIVE rule has historical examples below, use those real channel thumbnails as the FIRST packaging reference.',
      'Derive reusable text structure, hierarchy, composition, presenter/hero placement, and color treatment from the matching examples BEFORE inventing generic thumbnail packaging.',
      'Adapt the pattern to the new title/topic; never copy an old thumbnail sentence verbatim and never force an inapplicable medical or visual detail.',
      'If applicable historical examples exist, generic model preference (for example, automatically preferring very short text) must not outrank the channel pattern.',
      'Use generic best-practice only as fallback when no applicable ACTIVE pattern/example exists.','']
    if active.empty:
        lines.append('_No ACTIVE channel packaging rules yet._')
    else:
        for i,row in active.iterrows():
            rd = dict(row)
            label = f"Cluster — {row['feature_value']}" if str(row['feature_name']) == 'signal_cluster' else f"{row['feature_name']} = {row['feature_value']}"
            lines += [f"## Rule {i+1}: {label}",
              f"- **Context:** {row['context_type']} / {row['context_value']}",
              f"- **Guidance:** {row['guidance_text']}",
              f"- **Evidence:** {int(row['videos'])} videos / {float(row['total_impressions']):,.0f} impressions / CTR delta {float(row['ctr_delta_points']):+.2f} points"]
            examples = _rule_pattern_examples(db_path, rd, limit=6)
            if examples:
                lines += ['', '**Matching historical channel examples (pattern references, not copy templates):**']
                for ex in examples:
                    text = str(ex.get('thumbnail_text') or '').replace('\n', ' / ').strip() or '[no visible text]'
                    title = str(ex.get('title') or '').strip()
                    traits = _compact_pattern_traits(ex)
                    try: ctr = float(ex.get('ctr_percent'))
                    except Exception: ctr = None
                    try: imp = float(ex.get('impressions'))
                    except Exception: imp = None
                    perf = []
                    if ctr is not None: perf.append(f"CTR {ctr:.2f}%")
                    if imp is not None: perf.append(f"{imp:,.0f} impressions")
                    snapshot = str(ex.get('thumbnail_file_path') or '').strip()
                    source_note = 'source-cohort' if int(ex.get('_source_cohort_match') or 0) else 'matching-history'
                    tail = f" | archived={snapshot}" if snapshot else ""
                    lines.append(f"- **{text}** — {title} | {'; '.join(perf)} | {traits} | {source_note}{tail}")
            lines.append('')
    return "\n".join(lines).strip() + "\n"


def write_active_packaging_rules_file(db_path: Path, output_path: Path) -> dict[str, Any]:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_active_packaging_rules_markdown(db_path),
        encoding="utf-8",
        newline="\n",
    )
    return {'active':len(active_channel_packaging_rules(db_path)),'path':str(output_path)}

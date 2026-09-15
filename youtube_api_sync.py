from __future__ import annotations

import html
import io
import json
import re
import secrets
import threading
import urllib.parse
import urllib.request
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pandas as pd

from analytics_db import (
    AnalyticsDBError,
    _get_or_create_video_by_identity,
    import_retention_curve,
    import_youtube_csv,
    import_reach_report,
    processed_reporting_report_ids,
    needs_transcript_upload,
    snapshot_timestamped_transcript,
    _dedupe_caption_points,
    update_video_identity,
)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_API = "https://www.googleapis.com/youtube/v3"
YOUTUBE_ANALYTICS_API = "https://youtubeanalytics.googleapis.com/v2/reports"
YOUTUBE_REPORTING_API = "https://youtubereporting.googleapis.com/v1"
REACH_REPORT_TYPE_ID = "channel_reach_basic_a1"
OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
DEFAULT_CALLBACK_PORT = 53682


class YouTubeAPIError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise YouTubeAPIError(f"Could not read OAuth JSON: {exc}") from exc


def _client_config(client_json_path: Path) -> dict[str, Any]:
    payload = _read_json(client_json_path)
    cfg = payload.get("installed") or payload.get("web") or {}
    if not cfg.get("client_id") or not cfg.get("client_secret"):
        raise YouTubeAPIError("OAuth JSON must contain a Google Desktop app client_id and client_secret.")
    return cfg


def _form_post(url: str, values: dict[str, Any]) -> dict[str, Any]:
    data = urllib.parse.urlencode(values).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        detail = getattr(exc, "read", None)
        if callable(detail):
            try:
                body = detail().decode("utf-8", errors="replace")
                raise YouTubeAPIError(f"Google OAuth request failed: {body}") from exc
            except YouTubeAPIError:
                raise
            except Exception:
                pass
        raise YouTubeAPIError(f"Google OAuth request failed: {exc}") from exc


def _json_get(url: str, token: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        detail = getattr(exc, "read", None)
        if callable(detail):
            try:
                body = detail().decode("utf-8", errors="replace")
                raise YouTubeAPIError(f"YouTube API request failed: {body}") from exc
            except YouTubeAPIError:
                raise
            except Exception:
                pass
        raise YouTubeAPIError(f"YouTube API request failed: {exc}") from exc




def _json_post(url: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        detail = getattr(exc, "read", None)
        if callable(detail):
            try:
                body = detail().decode("utf-8", errors="replace")
                raise YouTubeAPIError(f"YouTube Reporting API request failed: {body}") from exc
            except YouTubeAPIError:
                raise
            except Exception:
                pass
        raise YouTubeAPIError(f"YouTube Reporting API request failed: {exc}") from exc


def _reporting_jobs(token: str) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    page_token = ""
    while True:
        params = {"pageSize": "50"}
        if page_token:
            params["pageToken"] = page_token
        data = _json_get(f"{YOUTUBE_REPORTING_API}/jobs?{urllib.parse.urlencode(params)}", token)
        jobs.extend(data.get("jobs") or [])
        page_token = str(data.get("nextPageToken") or "")
        if not page_token:
            break
    return jobs


def _ensure_reach_reporting_job(token: str) -> tuple[dict[str, Any], bool]:
    for job in _reporting_jobs(token):
        if str(job.get("reportTypeId") or "") == REACH_REPORT_TYPE_ID:
            return job, False
    created = _json_post(
        f"{YOUTUBE_REPORTING_API}/jobs",
        token,
        {"reportTypeId": REACH_REPORT_TYPE_ID, "name": "Senior Health AI Reach"},
    )
    return created, True


def _reporting_reports(token: str, job_id: str) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    page_token = ""
    while True:
        params = {"pageSize": "100"}
        if page_token:
            params["pageToken"] = page_token
        data = _json_get(
            f"{YOUTUBE_REPORTING_API}/jobs/{urllib.parse.quote(job_id)}/reports?"
            + urllib.parse.urlencode(params),
            token,
        )
        reports.extend(data.get("reports") or [])
        page_token = str(data.get("nextPageToken") or "")
        if not page_token:
            break
    return reports


def _download_csv(url: str, token: str) -> pd.DataFrame:
    raw = _raw_get(url, token)
    try:
        return pd.read_csv(io.BytesIO(raw))
    except Exception as exc:
        raise YouTubeAPIError(f"Could not parse YouTube Reporting CSV: {exc}") from exc


def _sync_reach_reporting(db_path: Path, token: str) -> dict[str, Any]:
    """Create/reuse the reach reporting job and import any unprocessed reports."""
    job, created = _ensure_reach_reporting_job(token)
    job_id = str(job.get("id") or "").strip()
    if not job_id:
        raise YouTubeAPIError("YouTube Reporting API did not return a reach job id.")

    reports = _reporting_reports(token, job_id)
    already = processed_reporting_report_ids(db_path, job_id)
    pending = [r for r in reports if str(r.get("id") or "") not in already]
    imported_reports = 0
    rows_written = 0
    unknown_video_ids = 0
    errors: list[str] = []

    # Process chronologically so later/backfill reports can replace the same day.
    pending.sort(key=lambda r: str(r.get("createTime") or ""))
    for report in pending:
        report_id = str(report.get("id") or "")
        download_url = str(report.get("downloadUrl") or "")
        if not download_url:
            continue
        try:
            df = _download_csv(download_url, token)
            imported = import_reach_report(
                db_path,
                job_id=job_id,
                report_type_id=REACH_REPORT_TYPE_ID,
                report_meta=report,
                df=df,
                source_file=f"youtube_reporting_api:{report_id}",
            )
            imported_reports += 1
            rows_written += int(imported.get("rows_written", 0))
            unknown_video_ids += int(imported.get("unknown_video_ids", 0))
        except Exception as exc:
            errors.append(f"reach report {report_id}: {exc}")

    return {
        "job_id": job_id,
        "job_created": created,
        "reports_available": len(reports),
        "reports_imported": imported_reports,
        "rows_written": rows_written,
        "unknown_video_ids": unknown_video_ids,
        "errors": errors,
        "waiting_for_first_report": bool(created and not reports),
    }



def _raw_get(url: str, token: str) -> bytes:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return response.read()
    except Exception as exc:
        detail = getattr(exc, "read", None)
        if callable(detail):
            try:
                body = detail().decode("utf-8", errors="replace")
                raise YouTubeAPIError(f"YouTube API request failed: {body}") from exc
            except YouTubeAPIError:
                raise
            except Exception:
                pass
        raise YouTubeAPIError(f"YouTube API request failed: {exc}") from exc


def _caption_tracks(token: str, video_id: str) -> list[dict[str, Any]]:
    q = urllib.parse.urlencode({"part": "snippet", "videoId": video_id})
    data = _json_get(f"{YOUTUBE_API}/captions?{q}", token)
    return list(data.get("items") or [])


def _pick_caption_track(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not items:
        return None

    def score(item: dict[str, Any]) -> tuple[int, int, int, str]:
        snippet = item.get("snippet") or {}
        language = str(snippet.get("language") or "").lower()
        track_kind = str(snippet.get("trackKind") or "").lower()
        is_draft = bool(snippet.get("isDraft"))
        is_auto = track_kind == "asr"
        english = 1 if language == "en" or language.startswith("en-") else 0
        manual = 1 if not is_auto else 0
        published = 1 if not is_draft else 0
        return (english, manual, published, str(item.get("id") or ""))

    return max(items, key=score)


_VTT_TIME_RE = re.compile(
    r"(?P<sh>\d{1,2}):(?P<sm>\d{2}):(?P<ss>\d{2})(?:[.,](?P<sms>\d{1,3}))?\s*-->\s*"
    r"(?P<eh>\d{1,2}):(?P<em>\d{2}):(?P<es>\d{2})(?:[.,](?P<ems>\d{1,3}))?"
)


def _caption_to_timestamped_text(raw: bytes) -> str:
    text = raw.decode("utf-8-sig", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    out: list[tuple[int, str]] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = _VTT_TIME_RE.search(line)
        if not m:
            i += 1
            continue
        h, minute, sec = int(m.group("sh")), int(m.group("sm")), int(m.group("ss"))
        start = h * 3600 + minute * 60 + sec
        i += 1
        cue: list[str] = []
        while i < len(lines) and lines[i].strip():
            body = lines[i].strip()
            if not body.isdigit() and "-->" not in body:
                body = re.sub(r"<[^>]+>", "", body)
                body = html.unescape(body)
                body = re.sub(r"\s+", " ", body).strip()
                if body:
                    cue.append(body)
            i += 1
        phrase = " ".join(cue).strip()
        if phrase:
            if out and out[-1][0] == start:
                if phrase not in out[-1][1]:
                    out[-1] = (start, (out[-1][1] + " " + phrase).strip())
            elif not out or phrase != out[-1][1]:
                out.append((start, phrase))
        i += 1

    if not out:
        raise YouTubeAPIError("Downloaded caption track did not contain timestamped cues.")

    cleaned = _dedupe_caption_points([{"start_sec": float(start), "text": phrase} for start, phrase in out])
    formatted = []
    for item in cleaned:
        start = int(item["start_sec"])
        phrase = str(item["text"] or "").strip()
        if not phrase:
            continue
        h = start // 3600
        m = (start % 3600) // 60
        s = start % 60
        formatted.append(f"[{h:02d}:{m:02d}:{s:02d}] {phrase}")
    return "\n".join(formatted)


def _fetch_and_store_caption_transcript(
    db_path: Path,
    analytics_id: str,
    token: str,
    video_id: str,
) -> dict[str, Any]:
    tracks = _caption_tracks(token, video_id)
    chosen = _pick_caption_track(tracks)
    if not chosen:
        return {"stored": False, "reason": "no_caption_track"}

    caption_id = str(chosen.get("id") or "").strip()
    if not caption_id:
        return {"stored": False, "reason": "no_caption_id"}

    url = f"{YOUTUBE_API}/captions/{urllib.parse.quote(caption_id)}?{urllib.parse.urlencode({'tfmt': 'vtt'})}"
    raw = _raw_get(url, token)
    timestamped = _caption_to_timestamped_text(raw)
    segments = snapshot_timestamped_transcript(db_path, analytics_id, timestamped)

    # Keep a permanent copy outside Projects so deleting a project folder cannot
    # remove the fallback transcript used by Analytics.
    asset_dir = Path(db_path).parent / "youtube_assets" / analytics_id
    asset_dir.mkdir(parents=True, exist_ok=True)
    (asset_dir / "youtube_captions.vtt").write_bytes(raw)
    (asset_dir / "timestamped_transcript.txt").write_text(timestamped, encoding="utf-8")

    snippet = chosen.get("snippet") or {}
    return {
        "stored": True,
        "segments": segments,
        "language": snippet.get("language"),
        "track_kind": snippet.get("trackKind"),
    }


def _save_token(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if path.is_file():
        try:
            existing = _read_json(path)
        except Exception:
            existing = {}
    merged = dict(existing)
    merged.update(payload)
    if not payload.get("refresh_token") and existing.get("refresh_token"):
        merged["refresh_token"] = existing["refresh_token"]
    path.write_text(json.dumps(merged, indent=2), encoding="utf-8")


def start_manual_oauth(
    client_json_path: Path,
    token_path: Path,
    pending_path: Path,
    *,
    port: int = DEFAULT_CALLBACK_PORT,
) -> str:
    """Start a loopback callback listener and return a URL the user can paste into IX Browser."""
    cfg = _client_config(client_json_path)
    redirect_uri = f"http://127.0.0.1:{int(port)}/youtube-oauth/callback"
    state = secrets.token_urlsafe(32)
    pending_path = Path(pending_path)
    pending_path.parent.mkdir(parents=True, exist_ok=True)
    pending_path.write_text(json.dumps({"state": state, "redirect_uri": redirect_uri}, indent=2), encoding="utf-8")

    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(OAUTH_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    authorization_url = GOOGLE_AUTH_URL + "?" + urllib.parse.urlencode(params)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            message = "YouTube connection failed. Return to Senior Health AI and try again."
            status = 400
            try:
                if query.get("state", [""])[0] != state:
                    raise YouTubeAPIError("OAuth state mismatch.")
                if query.get("error"):
                    raise YouTubeAPIError(query.get("error_description", query["error"])[0])
                code = query.get("code", [""])[0]
                if not code:
                    raise YouTubeAPIError("Google did not return an authorization code.")
                token = _form_post(
                    GOOGLE_TOKEN_URL,
                    {
                        "code": code,
                        "client_id": cfg["client_id"],
                        "client_secret": cfg["client_secret"],
                        "redirect_uri": redirect_uri,
                        "grant_type": "authorization_code",
                    },
                )
                _save_token(token_path, token)
                message = "YouTube connected successfully. You can close this tab and return to Senior Health AI."
                status = 200
            except Exception as exc:
                message = f"YouTube connection failed: {exc}"
            body = f"<html><body style='font-family:Arial;padding:40px'><h2>{message}</h2></body></html>".encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            try:
                pending_path.unlink(missing_ok=True)
            except Exception:
                pass
            threading.Thread(target=self.server.shutdown, daemon=True).start()

    try:
        server = HTTPServer(("127.0.0.1", int(port)), Handler)
    except OSError as exc:
        raise YouTubeAPIError(
            f"Could not start local OAuth callback on 127.0.0.1:{port}. Close any previous connection attempt and retry. ({exc})"
        ) from exc
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return authorization_url


def _access_token(client_json_path: Path, token_path: Path) -> str:
    cfg = _client_config(client_json_path)
    token = _read_json(token_path)
    refresh = str(token.get("refresh_token") or "").strip()
    if refresh:
        refreshed = _form_post(
            GOOGLE_TOKEN_URL,
            {
                "client_id": cfg["client_id"],
                "client_secret": cfg["client_secret"],
                "refresh_token": refresh,
                "grant_type": "refresh_token",
            },
        )
        _save_token(token_path, refreshed)
        return str(refreshed.get("access_token") or "")
    access = str(token.get("access_token") or "").strip()
    if not access:
        raise YouTubeAPIError("YouTube token is missing. Connect the channel again.")
    return access


def connection_status(client_json_path: Path, token_path: Path) -> dict[str, Any]:
    if not Path(client_json_path).is_file() or not Path(token_path).is_file():
        return {"connected": False}
    try:
        token = _access_token(client_json_path, token_path)
        q = urllib.parse.urlencode({"part": "snippet,contentDetails", "mine": "true"})
        data = _json_get(f"{YOUTUBE_API}/channels?{q}", token)
        items = data.get("items") or []
        if not items:
            return {"connected": False, "error": "No YouTube channel was found for this Google account."}
        item = items[0]
        return {
            "connected": True,
            "channel_id": item.get("id"),
            "channel_title": (item.get("snippet") or {}).get("title"),
            "uploads_playlist": ((item.get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads"),
        }
    except Exception as exc:
        return {"connected": False, "error": str(exc)}


def _iso8601_duration_seconds(value: str | None) -> float | None:
    import re
    if not value:
        return None
    m = re.fullmatch(r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", str(value))
    if not m:
        return None
    days, hours, minutes, seconds = m.groups()
    return (float(days or 0) * 86400 + float(hours or 0) * 3600 + float(minutes or 0) * 60 + float(seconds or 0))


def _analytics_query(token: str, *, start_date: str, end_date: str, metrics: str, filters: str, dimensions: str | None = None) -> dict[str, Any]:
    params = {
        "ids": "channel==MINE",
        "startDate": start_date,
        "endDate": end_date,
        "metrics": metrics,
        "filters": filters,
    }
    if dimensions:
        params["dimensions"] = dimensions
    return _json_get(YOUTUBE_ANALYTICS_API + "?" + urllib.parse.urlencode(params), token)


def _rows_as_dicts(report: dict[str, Any]) -> list[dict[str, Any]]:
    headers = [str(h.get("name")) for h in (report.get("columnHeaders") or [])]
    return [dict(zip(headers, row)) for row in (report.get("rows") or [])]


def _uploaded_videos(token: str, uploads_playlist: str) -> list[dict[str, Any]]:
    ids: list[str] = []
    page_token = ""
    while True:
        params = {"part": "contentDetails", "playlistId": uploads_playlist, "maxResults": "50"}
        if page_token:
            params["pageToken"] = page_token
        data = _json_get(f"{YOUTUBE_API}/playlistItems?{urllib.parse.urlencode(params)}", token)
        for item in data.get("items") or []:
            vid = ((item.get("contentDetails") or {}).get("videoId") or "").strip()
            if vid:
                ids.append(vid)
        page_token = str(data.get("nextPageToken") or "")
        if not page_token:
            break

    videos: list[dict[str, Any]] = []
    for start in range(0, len(ids), 50):
        batch = ids[start:start + 50]
        params = {"part": "snippet,contentDetails,status", "id": ",".join(batch), "maxResults": "50"}
        data = _json_get(f"{YOUTUBE_API}/videos?{urllib.parse.urlencode(params)}", token)
        videos.extend(data.get("items") or [])
    return videos


def sync_youtube_channel(db_path: Path, client_json_path: Path, token_path: Path) -> dict[str, Any]:
    """Sync uploaded channel videos, performance, and audience retention into the permanent DB.

    Local projects that have not been uploaded to YouTube are never imported by this routine.
    """
    status = connection_status(client_json_path, token_path)
    if not status.get("connected"):
        raise YouTubeAPIError(status.get("error") or "YouTube is not connected.")
    uploads = status.get("uploads_playlist")
    if not uploads:
        raise YouTubeAPIError("Could not resolve the channel uploads playlist.")
    token = _access_token(client_json_path, token_path)
    videos = _uploaded_videos(token, str(uploads))

    result = {
        "channel_title": status.get("channel_title"),
        "uploaded_videos": len(videos),
        "performance_synced": 0,
        "retention_synced": 0,
        "retention_unavailable": 0,
        "retention_diagnostics": [],
        "caption_transcripts_synced": 0,
        "caption_transcripts_unavailable": 0,
        "caption_reauthorization_required": False,
        "no_analytics_yet": 0,
        "reach_job_created": False,
        "reach_reports_available": 0,
        "reach_reports_imported": 0,
        "reach_rows_written": 0,
        "reach_waiting_for_first_report": False,
        "errors": [],
    }
    end_date = date.today().isoformat()
    caption_access_blocked = False

    for item in videos:
        video_id = str(item.get("id") or "").strip()
        snippet = item.get("snippet") or {}
        details = item.get("contentDetails") or {}
        title = str(snippet.get("title") or "").strip()
        published = str(snippet.get("publishedAt") or "")[:10]
        duration_sec = _iso8601_duration_seconds(details.get("duration"))
        start_date = published or "2005-02-14"
        try:
            aid = _get_or_create_video_by_identity(
                db_path,
                video_id=video_id,
                title=title,
                duration_sec=duration_sec,
                publish_date=published or None,
            )
            update_video_identity(
                db_path,
                aid,
                youtube_title=title,
                youtube_video_id=video_id,
                publish_date=published or None,
            )

            # Project folders are disposable. If no permanent Actual Timeline or
            # timestamped transcript exists, try the official YouTube Captions API
            # once and snapshot the transcript inside Analytics before retention
            # mapping. Existing Actual Timelines always remain the preferred source.
            if needs_transcript_upload(db_path, aid) and not caption_access_blocked:
                try:
                    transcript_result = _fetch_and_store_caption_transcript(
                        db_path, aid, token, video_id
                    )
                    if transcript_result.get("stored"):
                        result["caption_transcripts_synced"] += 1
                    else:
                        result["caption_transcripts_unavailable"] += 1
                except YouTubeAPIError as exc:
                    msg = str(exc)
                    if "insufficientPermissions" in msg or "insufficient authentication scopes" in msg.lower():
                        result["caption_reauthorization_required"] = True
                        caption_access_blocked = True
                    else:
                        result["errors"].append(f"{title}: caption transcript not stored ({exc})")

            perf_report = _analytics_query(
                token,
                start_date=start_date,
                end_date=end_date,
                metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,subscribersLost",
                filters=f"video=={video_id}",
            )
            perf_rows = _rows_as_dicts(perf_report)
            if perf_rows:
                p = perf_rows[0]
                gained = float(p.get("subscribersGained") or 0)
                lost = float(p.get("subscribersLost") or 0)
                df = pd.DataFrame([{
                    "Video title": title,
                    "Video ID": video_id,
                    "Video publish time": published,
                    "Duration": duration_sec,
                    "Views": p.get("views"),
                    "Watch time (hours)": (float(p.get("estimatedMinutesWatched") or 0) / 60.0),
                    "Average view duration": p.get("averageViewDuration"),
                    "Average percentage viewed (%)": p.get("averageViewPercentage"),
                    "Subscribers": gained - lost,
                }])
                import_youtube_csv(db_path, aid, df, source_file="youtube_api_sync")
                result["performance_synced"] += 1
            else:
                result["no_analytics_yet"] += 1

            # Absolute audience retention is the canonical curve used by the app.
            # Query it independently so optional relative-retention availability can
            # never prevent an otherwise valid curve from being stored.
            retention_report = _analytics_query(
                token,
                start_date=start_date,
                end_date=end_date,
                metrics="audienceWatchRatio",
                filters=f"video=={video_id}",
                dimensions="elapsedVideoTimeRatio",
            )
            retention_rows = _rows_as_dicts(retention_report)

            relative_by_position: dict[float, Any] = {}
            if len(retention_rows) >= 2:
                # Relative retention is enrichment only. Failure/unavailability here
                # must not block the absolute retention curve.
                try:
                    relative_report = _analytics_query(
                        token,
                        start_date=start_date,
                        end_date=end_date,
                        metrics="relativeRetentionPerformance",
                        filters=f"video=={video_id}",
                        dimensions="elapsedVideoTimeRatio",
                    )
                    for rr in _rows_as_dicts(relative_report):
                        pos = float(rr.get("elapsedVideoTimeRatio") or 0)
                        relative_by_position[pos] = rr.get("relativeRetentionPerformance")
                except Exception as exc:
                    result["retention_diagnostics"].append(
                        f"{video_id} · {title}: absolute retention available; optional relative retention unavailable ({exc})"
                    )

                rdf = pd.DataFrame([
                    {
                        "Video position (%)": float(r.get("elapsedVideoTimeRatio") or 0) * 100.0,
                        "Audience retention (%)": float(r.get("audienceWatchRatio") or 0) * 100.0,
                        "Relative retention": relative_by_position.get(float(r.get("elapsedVideoTimeRatio") or 0)),
                    }
                    for r in retention_rows
                ])
                try:
                    import_retention_curve(db_path, aid, rdf, source_file="youtube_api_sync")
                    result["retention_synced"] += 1
                except AnalyticsDBError as exc:
                    result["errors"].append(f"{title}: retention not stored ({exc})")
            else:
                result["retention_unavailable"] += 1
                result["retention_diagnostics"].append(
                    f"{video_id} · {title}: YouTube Analytics API returned {len(retention_rows)} absolute retention row(s); curve not stored."
                )
        except Exception as exc:
            result["errors"].append(f"{title or video_id}: {exc}")

    # Thumbnail impressions + CTR are provided by the YouTube Reporting API
    # reach report, not the targeted Analytics query above. The reporting job
    # is created once, then future syncs import only new/backfilled daily CSVs.
    try:
        reach = _sync_reach_reporting(db_path, token)
        result["reach_job_created"] = bool(reach.get("job_created"))
        result["reach_reports_available"] = int(reach.get("reports_available", 0))
        result["reach_reports_imported"] = int(reach.get("reports_imported", 0))
        result["reach_rows_written"] = int(reach.get("rows_written", 0))
        result["reach_waiting_for_first_report"] = bool(reach.get("waiting_for_first_report"))
        result["errors"].extend(reach.get("errors") or [])
    except Exception as exc:
        result["errors"].append(f"YouTube reach/CTR sync: {exc}")

    return result

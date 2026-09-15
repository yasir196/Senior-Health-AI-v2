from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from analytics_db import (
    AnalyticsDBError,
    get_video,
    latest_thumbnail_snapshot,
    record_thumbnail_analysis,
    thumbnail_inventory_df,
)

ANALYZER_VERSION = "thumbnail-stage2-v2-color"

SYSTEM_INSTRUCTION = """Analyze the supplied YouTube thumbnail as packaging, not as medical evidence.
Return JSON only. Be descriptive and neutral; do not predict CTR, quality scores, or causation.
Do not identify any real person. If a person is visible, call them presenter/person/older adult.
Read only text that is actually visible and preserve visible line breaks in thumbnail_text when possible.
Use null when a detail is not visually supportable or uncertain. Never fill a missing detail from the title.
For color fields, describe only clearly visible broad color families, not guessed exact hex values. dominant_palette should be a concise ordered string of 2-4 major color families (for example: dark navy | white | yellow | red). text_color_scheme should describe visible text colors only. accent_color_family is the main attention accent (for example red, yellow, green, none). palette_temperature must be warm, cool, mixed, neutral, or null. contrast_level must be high, medium, low, or null.
The public title is supplied only for title_thumbnail_relationship. That relationship must be one of:
duplicate, complementary, diverges, unclear, or null.
"""

FIELDS: dict[str, Any] = {
    "presenter_present": None,
    "presenter_position": None,
    "presenter_size": None,
    "expression": None,
    "gaze_target": None,
    "hero_subject": None,
    "hero_category": None,
    "hero_count": None,
    "thumbnail_text": None,
    "text_word_count": None,
    "text_line_count": None,
    "text_style": None,
    "question_hook": None,
    "number_hook": None,
    "arrow_present": None,
    "arrow_target": None,
    "background_style": None,
    "background_brightness": None,
    "background_color_family": None,
    "dominant_palette": None,
    "text_color_scheme": None,
    "accent_color_family": None,
    "palette_temperature": None,
    "contrast_level": None,
    "visual_complexity": None,
    "major_visual_object_count": None,
    "composition_layout": None,
    "subject_separation": None,
    "curiosity_mechanism": None,
    "title_thumbnail_relationship": None,
    "semantic_summary": None,
    "confidence": None,
}

_BOOLEAN_FIELDS = {"presenter_present", "question_hook", "number_hook", "arrow_present"}
_INTEGER_FIELDS = {"hero_count", "text_word_count", "text_line_count", "major_visual_object_count"}
_NUMBER_WORDS_RE = re.compile(
    r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|first|second|third)\b",
    flags=re.I,
)


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise RuntimeError("Vision response did not contain valid JSON.")
        obj = json.loads(match.group(0))
    if not isinstance(obj, dict):
        raise RuntimeError("Vision response JSON must be an object.")

    out = dict(FIELDS)
    for key in out:
        if key in obj:
            out[key] = obj[key]

    # Keep uncertainty explicit instead of coercing arbitrary strings to truthy values.
    for key in _BOOLEAN_FIELDS:
        value = out.get(key)
        if value is not None and not isinstance(value, bool):
            out[key] = None
    for key in _INTEGER_FIELDS:
        value = out.get(key)
        if value is None or isinstance(value, bool):
            if isinstance(value, bool):
                out[key] = None
            continue
        try:
            parsed = int(value)
            out[key] = parsed if parsed >= 0 else None
        except (TypeError, ValueError):
            out[key] = None

    confidence = out.get("confidence")
    if confidence is not None:
        try:
            confidence = float(confidence)
            out["confidence"] = confidence if 0.0 <= confidence <= 1.0 else None
        except (TypeError, ValueError):
            out["confidence"] = None

    relationship = out.get("title_thumbnail_relationship")
    if relationship is not None:
        normalized = str(relationship).strip().lower()
        aliases = {
            "duplicates": "duplicate",
            "duplicative": "duplicate",
            "complements": "complementary",
            "complement": "complementary",
            "divergent": "diverges",
            "diverge": "diverges",
            "unknown": "unclear",
        }
        normalized = aliases.get(normalized, normalized)
        out["title_thumbnail_relationship"] = (
            normalized if normalized in {"duplicate", "complementary", "diverges", "unclear"} else None
        )

    # Counts/hooks derived from the actually transcribed thumbnail text are more
    # reproducible than asking the model to do arithmetic.
    visible_text = out.get("thumbnail_text")
    if visible_text is not None:
        visible_text = str(visible_text).strip()
        out["thumbnail_text"] = visible_text or None
        if visible_text:
            words = re.findall(r"\b[\w’'-]+\b", visible_text, flags=re.UNICODE)
            lines = [line for line in visible_text.splitlines() if line.strip()]
            out["text_word_count"] = len(words)
            out["text_line_count"] = max(1, len(lines))
            out["question_hook"] = "?" in visible_text
            out["number_hook"] = bool(re.search(r"\d", visible_text) or _NUMBER_WORDS_RE.search(visible_text))
        else:
            out["text_word_count"] = 0
            out["text_line_count"] = 0
            out["question_hook"] = False
            out["number_hook"] = False
    out["analyzer_version"] = ANALYZER_VERSION
    return out


def _response_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return str(text)
    try:
        dumped = response.model_dump()
        chunks: list[str] = []
        for item in dumped.get("output", []):
            for content in item.get("content", []):
                if content.get("text"):
                    chunks.append(str(content["text"]))
        return "\n".join(chunks)
    except Exception:
        return str(response)


def _runtime_config() -> dict[str, Any]:
    path = Path(__file__).resolve().parent / "config.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _resolve_model(model: str | None) -> str:
    if model and str(model).strip():
        return str(model).strip()
    return str(_runtime_config().get("thumbnail_analysis_model") or "gpt-5.6-luna").strip()


def _openai_api_key() -> str:
    config = _runtime_config()
    env_name = str(config.get("openai_api_key_env") or "OPENAI_API_KEY").strip()
    return str(os.getenv(env_name) or "").strip()


def _verify_snapshot_file(snapshot: dict[str, Any]) -> tuple[Path, str]:
    path = Path(str(snapshot.get("file_path") or ""))
    if not path.is_file():
        raise AnalyticsDBError("Archived thumbnail file is missing.")
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    expected = str(snapshot.get("sha256") or "").strip().lower()
    if expected and digest.lower() != expected:
        raise AnalyticsDBError(
            "Archived thumbnail integrity check failed: file SHA256 no longer matches the stored snapshot."
        )
    return path, digest


def _analysis_paths(thumbnail_path: Path, snapshot_id: int, analyzed_at: str) -> tuple[Path, Path]:
    # Canonical structure: Analytics/youtube_assets/<analytics_id>/thumbnail_analysis/
    analysis_dir = thumbnail_path.parent.parent / "thumbnail_analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    stamp = re.sub(r"[^0-9]", "", analyzed_at)[:14] or datetime.now().strftime("%Y%m%d%H%M%S")
    versioned = analysis_dir / f"snapshot_{snapshot_id}_{stamp}.json"
    latest = analysis_dir / f"snapshot_{snapshot_id}.json"
    return versioned, latest


def analyze_thumbnail_snapshot(
    db_path: Path,
    analytics_id: str,
    *,
    model: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    snapshot = latest_thumbnail_snapshot(db_path, analytics_id)
    if not snapshot:
        raise AnalyticsDBError("No archived thumbnail exists for this video. Download it first.")
    thumbnail_path, actual_sha256 = _verify_snapshot_file(snapshot)
    snapshot_id = int(snapshot["id"])
    if str(snapshot.get("analysis_status") or "") == "analyzed" and not force:
        existing = thumbnail_analysis_df(db_path, analytics_id)
        if not existing.empty:
            try:
                payload = json.loads(str(existing.iloc[0].get("features_json") or "{}"))
            except Exception:
                payload = {}
            if payload.get("analyzer_version") == ANALYZER_VERSION:
                return {"status": "existing", "analytics_id": analytics_id, "snapshot_id": snapshot_id}
        # Analyzer schema gained packaging features (for example color intelligence).
        # Re-analyze this immutable snapshot once so old channel thumbnails are backfilled.

    video = get_video(db_path, analytics_id)
    if not video:
        raise AnalyticsDBError(f"Unknown analytics_id: {analytics_id}")
    title = str(
        video.get("youtube_title")
        or video.get("locked_title")
        or video.get("project_slug")
        or ""
    ).strip()
    resolved_model = _resolve_model(model)
    api_key = _openai_api_key()
    if not api_key:
        env_name = str(_runtime_config().get("openai_api_key_env") or "OPENAI_API_KEY")
        raise RuntimeError(f"{env_name} is not configured for thumbnail vision analysis.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("OpenAI Python package is not installed.") from exc

    mime = "image/png" if thumbnail_path.suffix.lower() == ".png" else "image/jpeg"
    encoded = base64.b64encode(thumbnail_path.read_bytes()).decode("ascii")
    data_url = f"data:{mime};base64,{encoded}"
    prompt = f"""Public YouTube title: {title or '[not available]'}

Return exactly one JSON object with these keys:
{json.dumps(FIELDS, ensure_ascii=False)}

Field guidance:
- presenter_position: left / center / right / mixed / null.
- presenter_size: close-up / medium / small / null.
- hero_subject: concise literal description of the dominant subject.
- hero_category: food / exercise / body_region / object / person / anatomy / mixed / other / null.
- hero_count: count only major hero subjects, not tiny decorative details.
- thumbnail_text: exact visible thumbnail wording; preserve line breaks when supportable.
- text_style: concise visible hierarchy/color treatment; no quality judgment.
- background_style: literal background description.
- background_brightness: dark / medium / bright / mixed / null.
- visual_complexity: low / medium / high / null.
- major_visual_object_count: count major readable visual objects/people, not tiny decoration.
- composition_layout: concise spatial layout, e.g. 'presenter right, hero left, text upper-left'.
- subject_separation: low / medium / high / null, describing visible foreground/background separation or contrast only.
- curiosity_mechanism: neutral description of the information gap, comparison, question, reveal, etc.; null if unsupported.
- title_thumbnail_relationship: duplicate / complementary / diverges / unclear / null. Use the title only for this field.
- confidence: 0 to 1 overall extraction confidence.

Do not infer medical outcomes, creator intent, CTR performance, or facts hidden outside the image."""

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=resolved_model,
        input=[
            {"role": "system", "content": [{"type": "input_text", "text": SYSTEM_INSTRUCTION}]},
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": data_url},
                ],
            },
        ],
    )
    raw_response = _response_text(response)
    features = _extract_json(raw_response)
    analyzed_at = datetime.now().isoformat(timespec="seconds")

    record_thumbnail_analysis(
        db_path,
        snapshot_id,
        analytics_id=analytics_id,
        youtube_video_id=str(snapshot["youtube_video_id"]),
        analyzed_at=analyzed_at,
        model=resolved_model,
        title_at_analysis=title,
        features=features,
        raw_response=raw_response,
    )

    versioned_path, latest_path = _analysis_paths(thumbnail_path, snapshot_id, analyzed_at)
    payload = {
        "analyzer_version": ANALYZER_VERSION,
        "analytics_id": analytics_id,
        "youtube_video_id": snapshot["youtube_video_id"],
        "thumbnail_snapshot_id": snapshot_id,
        "thumbnail_file": str(thumbnail_path.resolve()),
        "thumbnail_sha256": actual_sha256,
        "snapshot_downloaded_at": snapshot.get("downloaded_at"),
        "analyzed_at": analyzed_at,
        "model": resolved_model,
        "title_at_analysis": title,
        "features": features,
        "raw_response": raw_response,
    }
    serialized = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    versioned_path.write_text(serialized, encoding="utf-8")
    latest_path.write_text(serialized, encoding="utf-8")
    return {
        "status": "analyzed",
        "analytics_id": analytics_id,
        "snapshot_id": snapshot_id,
        "features": features,
        "analysis_path": str(latest_path.resolve()),
        "analysis_history_path": str(versioned_path.resolve()),
    }


def analyze_pending_thumbnails(db_path: Path, *, model: str | None = None) -> dict[str, Any]:
    inventory = thumbnail_inventory_df(db_path)
    result: dict[str, Any] = {"checked": 0, "analyzed": 0, "existing": 0, "failed": 0, "errors": []}
    if inventory.empty:
        return result
    for row in inventory.to_dict("records"):
        if not str(row.get("file_path") or "").strip():
            continue
        result["checked"] += 1
        try:
            item = analyze_thumbnail_snapshot(db_path, str(row["analytics_id"]), model=model, force=False)
            result[item["status"]] = int(result.get(item["status"], 0)) + 1
        except Exception as exc:
            result["failed"] += 1
            result["errors"].append(f"{row.get('youtube_video_id')}: {exc}")
    return result

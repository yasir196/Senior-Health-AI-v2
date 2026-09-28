from __future__ import annotations

import base64
import json
import urllib.request
from pathlib import Path
from typing import Any

from Thumbnail_Pipeline.adapters.youtube_thumbnail_analysis import analyze_youtube_reference_thumbnail
from Thumbnail_Pipeline.io_policy import safe_output


def youtube_thumbnail_url(video_id: str) -> str:
    vid=str(video_id or "").strip()
    if not vid:
        raise ValueError("Winner video ID is required.")
    return f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg"


def openai_winner_metadata_analyzer(api_key: str, *, model: str = "gpt-5-mini", timeout: int = 90):
    """Create fresh, detailed machine-readable metadata from the selected winner image only."""
    key=str(api_key or "").strip()
    if not key:
        raise ValueError("OpenAI API key is required for winner metadata extraction.")

    def analyze(path: Path, source: dict[str, Any]) -> dict[str, Any]:
        raw=Path(path).read_bytes()
        data_url="data:image/jpeg;base64,"+base64.b64encode(raw).decode("ascii")
        instruction="""Inspect ONLY the supplied winning YouTube thumbnail pixels. Produce detailed reusable thumbnail metadata as JSON. Do not infer visual facts from the video title, CTR, topic, or other thumbnails. Describe what is visibly present, including exact visible text when readable, canvas/background, full composition, text/visual split, banners, text zones, primary/secondary visuals, presenter/human presence, arrows/circles/boxes/highlights, typography, colors, visual hierarchy, semantic hook structure supported by visible copy, approximate percentage geometry, density, thumbnail patterns, and a reusable_composition_contract. The reusable contract must preserve composition/style roles while clearly separating topic-specific objects/words from reusable structure. Never invent an element that is not visible. Use null/unknown when uncertain. Font slant must be based on pixels only. Return one JSON object only."""
        payload={"model":model,"input":[{"role":"user","content":[{"type":"input_text","text":instruction},{"type":"input_image","image_url":data_url}]}]}
        req=urllib.request.Request("https://api.openai.com/v1/responses",data=json.dumps(payload).encode("utf-8"),headers={"Authorization":f"Bearer {key}","Content-Type":"application/json","User-Agent":"SeniorHealthAI-ThumbnailPipeline/1.0"},method="POST")
        with urllib.request.urlopen(req,timeout=timeout) as response:
            body=json.loads(response.read().decode("utf-8"))
        output_text=str(body.get("output_text") or "").strip()
        if not output_text:
            for item in body.get("output") or []:
                for part in item.get("content") or []:
                    if part.get("type")=="output_text":
                        output_text=str(part.get("text") or "").strip()
                        if output_text: break
                if output_text: break
        if output_text.startswith("```"):
            output_text=output_text.strip().strip("`")
            if output_text.lower().startswith("json"):
                output_text=output_text[4:].lstrip()
        metadata=json.loads(output_text)
        if not isinstance(metadata,dict):
            raise ValueError("Winner metadata analyzer must return a JSON object.")
        metadata["source"]={
            "selection_source":source.get("selection_source"),
            "video_id":source.get("video_id"),
            "video_url":source.get("video_url"),
            "title":source.get("title"),
            "ctr":source.get("ctr"),
            "impressions":source.get("impressions"),
            "fresh_thumbnail_path":str(path),
            "metadata_fresh_each_run":True,
        }
        return metadata
    return analyze


def build_fresh_winner_metadata(*, project: str, selected_layout: dict[str, Any], youtube_rows: list[dict[str, Any]], metadata_analyzer=None) -> dict[str, Any]:
    """Fresh-download exactly the selected winner thumbnail and save its fresh metadata JSON."""
    selected=selected_layout or {}
    if selected.get("winner_video_id"):
        video_id=str(selected["winner_video_id"])
        source={
            "selection_source":"db_winner",
            "video_id":video_id,
            "video_url":selected.get("winner_video_url") or f"https://www.youtube.com/watch?v={video_id}",
            "title":selected.get("winner_title"),
            "ctr":selected.get("winner_ctr"),
            "impressions":selected.get("winner_impressions"),
            "thumbnail_url_or_path":youtube_thumbnail_url(video_id),
        }
    elif selected.get("youtube_match_video_id"):
        video_id=str(selected["youtube_match_video_id"])
        matched=next((r for r in youtube_rows if str(r.get("video_id") or "")==video_id),{})
        source={
            "selection_source":"youtube_fallback",
            "video_id":video_id,
            "video_url":f"https://www.youtube.com/watch?v={video_id}",
            "title":matched.get("video_title"),
            "ctr":None,
            "impressions":None,
            "thumbnail_url_or_path":youtube_thumbnail_url(video_id),
        }
    else:
        return {"status":"unavailable","reason":"selected_layout_has_no_video_id"}

    winner_dir=safe_output(Path(project)/"winner_thumbnail")
    json_dir=safe_output(Path(project)/"json")
    winner_dir.mkdir(parents=True,exist_ok=True); json_dir.mkdir(parents=True,exist_ok=True)
    # The shared downloader intentionally accepts only a direct project folder name.
    # Download there first, then move the selected winner into its dedicated subfolder.
    downloaded=analyze_youtube_reference_thumbnail(source,project=project,text_analyzer=None)
    local=downloaded.get("local_thumbnail_path")
    if not local:
        return {"status":"failed","reason":downloaded.get("thumbnail_analysis_reason") or "winner_thumbnail_download_failed","source":source}
    downloaded_path=Path(local)
    winner_path=winner_dir/f"{video_id}{downloaded_path.suffix or '.jpg'}"
    if downloaded_path.resolve()!=winner_path.resolve():
        winner_path.write_bytes(downloaded_path.read_bytes())
        downloaded_path.unlink()
    local=str(winner_path)
    if metadata_analyzer is None:
        return {"status":"downloaded_metadata_unavailable","source":source,"thumbnail_path":local}
    metadata=metadata_analyzer(winner_path,source)
    metadata_path=json_dir/"winner_metadata.json"
    metadata_path.write_text(json.dumps(metadata,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return {"status":"ready","source":source,"thumbnail_path":local,"metadata_path":str(metadata_path),"metadata":metadata}

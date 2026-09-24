from __future__ import annotations
import hashlib, urllib.request
from pathlib import Path
from typing import Any
from Thumbnail_Pipeline.io_policy import safe_output
from Thumbnail_Pipeline.analyzer.features import analyze_image
from Thumbnail_Pipeline.analyzer.ocr import analyze_text

def analyze_youtube_reference_thumbnail(reference:dict[str,Any],*,timeout:int=30)->dict[str,Any]:
    """Download a public YouTube thumbnail into pipeline outputs and inspect it locally."""
    url=str(reference.get("thumbnail_url_or_path") or "").strip()
    if not url.startswith(("https://","http://")):
        return {**reference,"thumbnail_analysis_status":"unavailable","thumbnail_analysis_reason":"no_public_thumbnail_url"}
    vid=str(reference.get("video_id") or hashlib.sha256(url.encode()).hexdigest()[:16])
    target=safe_output(Path("youtube_references")/f"{vid}.jpg")
    target.parent.mkdir(parents=True,exist_ok=True)
    req=urllib.request.Request(url,headers={"User-Agent":"SeniorHealthAI-ThumbnailPipeline/1.0"})
    with urllib.request.urlopen(req,timeout=timeout) as response:
        data=response.read()
    target.write_bytes(data)
    try:
        features=analyze_image(target); ocr=analyze_text(target)
    except Exception as exc:
        return {**reference,"local_thumbnail_path":str(target),"thumbnail_analysis_status":"failed","thumbnail_analysis_reason":str(exc)}
    return {**reference,"local_thumbnail_path":str(target),"thumbnail_analysis_status":"analyzed","external_thumbnail_features":features,"external_thumbnail_ocr":ocr}

def analyze_youtube_reference_thumbnails(references:list[dict[str,Any]])->list[dict[str,Any]]:
    out=[]
    for ref in references:
        try: out.append(analyze_youtube_reference_thumbnail(ref))
        except Exception as exc: out.append({**ref,"thumbnail_analysis_status":"failed","thumbnail_analysis_reason":str(exc)})
    return out

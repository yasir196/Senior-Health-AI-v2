from __future__ import annotations
import base64, hashlib, json, urllib.request, urllib.parse
from pathlib import Path
from typing import Any
from Thumbnail_Pipeline.io_policy import safe_output
from Thumbnail_Pipeline.analyzer.features import analyze_image
from Thumbnail_Pipeline.analyzer.ocr import analyze_text

MAX_THUMBNAIL_BYTES=8*1024*1024
ALLOWED_THUMBNAIL_HOST_SUFFIXES=("ytimg.com","youtube.com")

def openai_thumbnail_text_analyzer(api_key:str,*,model:str="gpt-5-mini",timeout:int=60):
    """Return a callable that transcribes visible copy and its coarse placement only.

    Placement is descriptive visual evidence, not a CTR claim. The model must not infer
    from the video title/topic and may return unknown when the text region is ambiguous.
    """
    key=str(api_key or "").strip()
    if not key:
        raise ValueError("OpenAI API key is required for vision thumbnail text analysis.")
    def analyze(path:Path,reference:dict[str,Any])->dict[str,Any]:
        raw=Path(path).read_bytes()
        data_url="data:image/jpeg;base64,"+base64.b64encode(raw).decode("ascii")
        payload={
            "model":model,
            "input":[{
                "role":"user",
                "content":[
                    {"type":"input_text","text":"Inspect ONLY this YouTube thumbnail. Transcribe the visibly printed thumbnail text, preserving words, punctuation, and line breaks. Also classify where the main text block is visibly placed: left, center, right, or unknown. Do not infer either field from the video title, objects, or topic. If text is unreadable return empty text; if placement is ambiguous return unknown. Return JSON only."},
                    {"type":"input_image","image_url":data_url},
                ],
            }],
            "text":{"format":{"type":"json_schema","name":"thumbnail_visual_text","strict":True,"schema":{"type":"object","properties":{"text":{"type":"string"},"text_placement":{"type":"string","enum":["left","center","right","unknown"]}},"required":["text","text_placement"],"additionalProperties":False}}},
        }
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
        parsed=json.loads(output_text) if output_text else {"text":"","text_placement":"unknown"}
        placement=str(parsed.get("text_placement") or "unknown").lower()
        if placement not in {"left","center","right"}: placement="unknown"
        return {"text":str(parsed.get("text") or "").strip(),"text_placement":placement,"source":"openai_vision","model":model}
    return analyze

def analyze_youtube_reference_thumbnail(reference:dict[str,Any],*,timeout:int=30,text_analyzer=None)->dict[str,Any]:
    """Download a public YouTube thumbnail into pipeline outputs and inspect it locally."""
    url=str(reference.get("thumbnail_url_or_path") or "").strip()
    parsed=urllib.parse.urlparse(url)
    host=(parsed.hostname or "").lower()
    if parsed.scheme!="https" or not any(host==suffix or host.endswith("."+suffix) for suffix in ALLOWED_THUMBNAIL_HOST_SUFFIXES):
        return {**reference,"thumbnail_analysis_status":"unavailable","thumbnail_analysis_reason":"untrusted_thumbnail_url"}
    vid=str(reference.get("video_id") or hashlib.sha256(url.encode()).hexdigest()[:16])
    target=safe_output(Path("youtube_references")/f"{vid}.jpg")
    target.parent.mkdir(parents=True,exist_ok=True)
    req=urllib.request.Request(url,headers={"User-Agent":"SeniorHealthAI-ThumbnailPipeline/1.0"})
    with urllib.request.urlopen(req,timeout=timeout) as response:
        declared=response.headers.get("Content-Length")
        if declared and int(declared)>MAX_THUMBNAIL_BYTES:
            return {**reference,"thumbnail_analysis_status":"failed","thumbnail_analysis_reason":"thumbnail_too_large"}
        data=response.read(MAX_THUMBNAIL_BYTES+1)
        if len(data)>MAX_THUMBNAIL_BYTES:
            return {**reference,"thumbnail_analysis_status":"failed","thumbnail_analysis_reason":"thumbnail_too_large"}
    target.write_bytes(data)
    try:
        features=analyze_image(target); ocr=analyze_text(target)
        visual_text=None
        visual_text_placement=None
        if text_analyzer is not None and (not isinstance(ocr,dict) or not str(ocr.get("text") or "").strip()):
            candidate=text_analyzer(target,reference)
            if isinstance(candidate,dict):
                visual_text=str(candidate.get("text") or "").strip() or None
                placement=str(candidate.get("text_placement") or "").strip().lower()
                visual_text_placement=placement if placement in {"left","center","right"} else None
            elif candidate is not None:
                visual_text=str(candidate).strip() or None
    except Exception as exc:
        return {**reference,"local_thumbnail_path":str(target),"thumbnail_analysis_status":"failed","thumbnail_analysis_reason":str(exc)}
    return {**reference,"local_thumbnail_path":str(target),"thumbnail_analysis_status":"analyzed","external_thumbnail_features":features,"external_thumbnail_ocr":ocr,"external_thumbnail_visual_text":visual_text,"external_thumbnail_text_placement":visual_text_placement}

def analyze_youtube_reference_thumbnails(references:list[dict[str,Any]],*,text_analyzer=None)->list[dict[str,Any]]:
    out=[]
    for ref in references:
        try: out.append(analyze_youtube_reference_thumbnail(ref,text_analyzer=text_analyzer))
        except Exception as exc: out.append({**ref,"thumbnail_analysis_status":"failed","thumbnail_analysis_reason":str(exc)})
    return out

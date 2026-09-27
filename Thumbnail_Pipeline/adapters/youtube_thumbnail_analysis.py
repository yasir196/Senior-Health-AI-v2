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
                    {"type":"input_text","text":"Inspect ONLY this YouTube thumbnail. Transcribe the visibly printed thumbnail text, preserving words, punctuation, and line breaks. Also classify where the main text block is visibly placed: left, center, right, or unknown. Classify the coarse structural layout ONLY when visibly clear, using exactly one of: text_left_subject_right, subject_left_text_right, text_top_subject_bottom, subject_top_text_bottom, centered_subject, unknown. Also describe the main visibly depicted subject in a short literal noun phrase (for example, coffee cup with cloves); use empty string if no clear subject. Additionally return a structural_signature using only visible geometry: text_zone, primary_visual_zone, presenter_zone, and secondary_visual_zone. Each zone must be one of upper-left, upper-center, upper-right, center-left, center, center-right, lower-left, lower-center, lower-right, none, unknown. primary_visual_zone is the dominant non-text topic visual; presenter_zone is a clearly visible human presenter/face when present; secondary_visual_zone is a distinct secondary non-text visual when present. Do not infer roles from the title/topic. This subject must come only from visible pixels, never from the video title/topic. This layout describes regions only; never put object names into the layout field. Do not infer any field from the video title or topic. If text is unreadable return empty text; if placement/layout is ambiguous return unknown. Return JSON only."},
                    {"type":"input_image","image_url":data_url},
                ],
            }],
            "text":{"format":{"type":"json_schema","name":"thumbnail_visual_text","strict":True,"schema":{"type":"object","properties":{"text":{"type":"string"},"text_placement":{"type":"string","enum":["left","center","right","unknown"]},"structural_layout":{"type":"string","enum":["text_left_subject_right","subject_left_text_right","text_top_subject_bottom","subject_top_text_bottom","centered_subject","unknown"]},"visible_subject":{"type":"string"},"structural_signature":{"type":"object","properties":{"text_zone":{"type":"string","enum":["upper-left","upper-center","upper-right","center-left","center","center-right","lower-left","lower-center","lower-right","none","unknown"]},"primary_visual_zone":{"type":"string","enum":["upper-left","upper-center","upper-right","center-left","center","center-right","lower-left","lower-center","lower-right","none","unknown"]},"presenter_zone":{"type":"string","enum":["upper-left","upper-center","upper-right","center-left","center","center-right","lower-left","lower-center","lower-right","none","unknown"]},"secondary_visual_zone":{"type":"string","enum":["upper-left","upper-center","upper-right","center-left","center","center-right","lower-left","lower-center","lower-right","none","unknown"]}},"required":["text_zone","primary_visual_zone","presenter_zone","secondary_visual_zone"],"additionalProperties":False}}},"required":["text","text_placement","structural_layout","visible_subject","structural_signature"],"additionalProperties":False}}},
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
        parsed=json.loads(output_text) if output_text else {"text":"","text_placement":"unknown","structural_layout":"unknown","visible_subject":""}
        placement=str(parsed.get("text_placement") or "unknown").lower()
        if placement not in {"left","center","right"}: placement="unknown"
        layout=str(parsed.get("structural_layout") or "unknown").lower()
        allowed_layouts={"text_left_subject_right","subject_left_text_right","text_top_subject_bottom","subject_top_text_bottom","centered_subject"}
        if layout not in allowed_layouts: layout="unknown"
        zone_values={"upper-left","upper-center","upper-right","center-left","center","center-right","lower-left","lower-center","lower-right","none","unknown"}
        signature=parsed.get("structural_signature") if isinstance(parsed.get("structural_signature"),dict) else {}
        signature={k:(str(signature.get(k) or "unknown").lower() if str(signature.get(k) or "unknown").lower() in zone_values else "unknown") for k in ("text_zone","primary_visual_zone","presenter_zone","secondary_visual_zone")}
        return {"text":str(parsed.get("text") or "").strip(),"text_placement":placement,"structural_layout":layout,"visible_subject":str(parsed.get("visible_subject") or "").strip(),"structural_signature":signature,"source":"openai_vision","model":model}
    return analyze

def clear_youtube_reference_thumbnails(project:str)->dict[str,Any]:
    """Delete only this project's cached YouTube reference thumbnails before a fresh run."""
    project_name=str(project or "").strip()
    if not project_name or Path(project_name).name != project_name or project_name in {".",".."}:
        raise ValueError("A safe direct project folder name is required for YouTube thumbnail output.")
    target_dir=safe_output(Path(project_name))
    removed=0
    if target_dir.is_dir():
        for path in target_dir.iterdir():
            if path.is_file() and path.suffix.lower() in {".jpg",".jpeg",".png",".webp"}:
                path.unlink()
                removed+=1
    return {"project":project_name,"removed_thumbnail_files":removed,"output_dir":str(target_dir)}

def analyze_youtube_reference_thumbnail(reference:dict[str,Any],*,project:str,timeout:int=30,text_analyzer=None)->dict[str,Any]:
    """Download a public YouTube thumbnail into pipeline outputs and inspect it locally."""
    url=str(reference.get("thumbnail_url_or_path") or "").strip()
    parsed=urllib.parse.urlparse(url)
    host=(parsed.hostname or "").lower()
    if parsed.scheme!="https" or not any(host==suffix or host.endswith("."+suffix) for suffix in ALLOWED_THUMBNAIL_HOST_SUFFIXES):
        return {**reference,"thumbnail_analysis_status":"unavailable","thumbnail_analysis_reason":"untrusted_thumbnail_url"}
    project_name=str(project or "").strip()
    if not project_name or Path(project_name).name != project_name or project_name in {".",".."}:
        raise ValueError("A safe direct project folder name is required for YouTube thumbnail output.")
    vid=str(reference.get("video_id") or hashlib.sha256(url.encode()).hexdigest()[:16])
    target=safe_output(Path(project_name)/f"{vid}.jpg")
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
        visual_structural_layout=None
        visual_subject=None
        visual_structural_signature=None
        if text_analyzer is not None and (not isinstance(ocr,dict) or not str(ocr.get("text") or "").strip()):
            candidate=text_analyzer(target,reference)
            if isinstance(candidate,dict):
                visual_text=str(candidate.get("text") or "").strip() or None
                placement=str(candidate.get("text_placement") or "").strip().lower()
                visual_text_placement=placement if placement in {"left","center","right"} else None
                layout=str(candidate.get("structural_layout") or "").strip().lower()
                visual_structural_layout=layout if layout in {"text_left_subject_right","subject_left_text_right","text_top_subject_bottom","subject_top_text_bottom","centered_subject"} else None
                visual_subject=str(candidate.get("visible_subject") or "").strip() or None
                signature=candidate.get("structural_signature")
                visual_structural_signature=signature if isinstance(signature,dict) else None
            elif candidate is not None:
                visual_text=str(candidate).strip() or None
    except Exception as exc:
        return {**reference,"local_thumbnail_path":str(target),"thumbnail_analysis_status":"failed","thumbnail_analysis_reason":str(exc)}
    return {**reference,"local_thumbnail_path":str(target),"thumbnail_analysis_status":"analyzed","external_thumbnail_features":features,"external_thumbnail_ocr":ocr,"external_thumbnail_visual_text":visual_text,"external_thumbnail_text_placement":visual_text_placement,"external_thumbnail_structural_layout":visual_structural_layout,"external_thumbnail_visible_subject":visual_subject,"external_thumbnail_structural_signature":visual_structural_signature}

def analyze_youtube_reference_thumbnails(references:list[dict[str,Any]],*,project:str,text_analyzer=None)->list[dict[str,Any]]:
    out=[]
    for ref in references:
        try: out.append(analyze_youtube_reference_thumbnail(ref,project=project,text_analyzer=text_analyzer))
        except Exception as exc: out.append({**ref,"thumbnail_analysis_status":"failed","thumbnail_analysis_reason":str(exc)})
    return out

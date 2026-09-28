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
        # Structured Outputs prevents long vision responses from producing malformed JSON.
        # Keep the schema intentionally flexible inside each major section so fresh visual
        # details are preserved rather than forcing a brittle fixed thumbnail template.
        metadata_schema={
            "type":"object",
            "properties":{
                "asset_type":{"type":["string","null"]},
                "content_category":{"type":["string","null"]},
                "topic":{"type":["string","null"]},
                "visual_style":{"type":["string","null"]},
                "canvas":{"type":"object","additionalProperties":True},
                "composition":{"type":"object","additionalProperties":True},
                "text":{"type":"object","additionalProperties":True},
                "color_system":{"type":"object","additionalProperties":True},
                "primary_visual":{"type":"object","additionalProperties":True},
                "secondary_visual":{"type":"object","additionalProperties":True},
                "attention_devices":{"type":"object","additionalProperties":True},
                "visual_hierarchy":{"type":"object","additionalProperties":True},
                "semantic_structure":{"type":"object","additionalProperties":True},
                "layout_geometry":{"type":"object","additionalProperties":True},
                "design_density":{"type":"object","additionalProperties":True},
                "thumbnail_pattern":{"type":"object","additionalProperties":True},
                "reusable_composition_contract":{"type":"object","additionalProperties":True}
            },
            "required":["asset_type","content_category","topic","visual_style","canvas","composition","text","color_system","primary_visual","secondary_visual","attention_devices","visual_hierarchy","semantic_structure","layout_geometry","design_density","thumbnail_pattern","reusable_composition_contract"],
            "additionalProperties":False
        }
        payload={
            "model":model,
            "input":[{"role":"user","content":[{"type":"input_text","text":instruction},{"type":"input_image","image_url":data_url}]}],
            "text":{"format":{"type":"json_schema","name":"winner_thumbnail_metadata","strict":False,"schema":metadata_schema}}
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




def _sanitize_topic_adaptation(adapted: dict[str, Any], *, immutable_title: str, selected_text: str | None) -> dict[str, Any]:
    """Deterministically remove unsupported claims and visual specifics from AI slot adaptation."""
    import re
    out=dict(adapted or {})
    title=str(immutable_title or "")
    title_l=title.casefold()
    title_tokens=set(re.findall(r"[a-z0-9]+",title_l))
    blocked_claims=("fix","cure","reverse","secret","eliminate","guaranteed","all you need")
    for key in ("top_banner","boxed_keyword","bottom_callout"):
        value=out.get(key)
        if isinstance(value,str) and any(re.search(r"\\b"+re.escape(term)+r"\\b",value,flags=re.I) for term in blocked_claims):
            out[key]=None
    if selected_text:
        out["primary_headline"]=str(selected_text).strip()

    visual_text=" ".join(str(out.get(k) or "") for k in ("primary_visual","secondary_detail","attention_target"))
    visual_l=visual_text.casefold()

    # Concrete dosage forms and packaging are allowed only when the immutable title
    # explicitly names that form. A generic nutrient/supplement title is not enough.
    gated_groups={
        "dosage_form":{
            "capsule":{"capsule","capsules"},
            "tablet":{"tablet","tablets"},
            "pill":{"pill","pills"},
            "softgel":{"softgel","softgels"},
            "gummy":{"gummy","gummies"},
            "powder":{"powder","powders"},
        },
        "packaging":{
            "bottle":{"bottle","bottles"},
            "container":{"container","containers"},
            "jar":{"jar","jars"},
            "packet":{"packet","packets"},
            "sachet":{"sachet","sachets"},
        },
    }
    violates=False
    for group in gated_groups.values():
        for forms in group.values():
            if any(re.search(r"\\b"+re.escape(form)+r"\\b",visual_l) for form in forms) and not (forms & title_tokens):
                violates=True
                break
        if violates:
            break

    # Never infer these product-specific attributes unless literally supported by title text.
    if not violates:
        always_gated={
            "imprint":r"\\b(?:imprint|imprinted|engraved|marking)\\b",
            "dosage":r"\\b\\d+(?:\\.\\d+)?\\s*(?:mg|mcg|g|ml|iu)\\b",
            "brand":r"\\b(?:brand(?:ed)?|logo)\\b",
        }
        for pattern in always_gated.values():
            if re.search(pattern,visual_l,flags=re.I) and not re.search(pattern,title_l,flags=re.I):
                violates=True
                break

    if violates:
        # For a clearly named nutrient/supplement with no title-supported dosage form,
        # use one generic unbranded bottle instead of inventing tablets/capsules/powder.
        topic_tokens=[t for t in title_tokens if len(t)>3 and t not in {"over","your","isn","working","nighttime","mistakes"}]
        subject="magnesium" if "magnesium" in title_tokens else (" ".join(topic_tokens[:2]) if topic_tokens else "the current-topic subject")
        label=subject.upper()
        out["primary_visual"]=f"Close-up of one generic unbranded supplement bottle on the right labeled only '{label}'. Do not show or imply capsules, tablets, pills, powder, gummies, softgels, dosage, brand, logo, color-specific product details, or other invented product specifics."
        out["secondary_detail"]=f"Close-up detail of the '{label}' ingredient label on the same generic bottle; no separate dosage form, scoop, spoon, dropper, loose product, or additional packaging."
        out["attention_target"]="Preserve the winner's circle/arrow attention pattern and point it to the ingredient label/detail on that same generic bottle."
    return out

def openai_current_topic_adapter(api_key: str, *, model: str = "gpt-5-mini", timeout: int = 90):
    """Adapt winner composition slots to the current immutable title without mixing references."""
    key=str(api_key or "").strip()
    if not key:
        raise ValueError("OpenAI API key is required for current-topic adaptation.")

    def adapt(*, metadata: dict[str, Any], immutable_title: str, selected_text: str | None) -> dict[str, Any]:
        instruction="""You are adapting a proven YouTube thumbnail composition to ONE current video topic.
Use the supplied winner metadata ONLY for reusable visual structure, geometry, hierarchy, palette, typography roles, and attention-device roles.
Use ONLY CURRENT_TITLE and SELECTED_THUMBNAIL_TEXT for current-topic semantics. Never carry historical winner topic words or objects into the adapted content.
Do not use or combine subjects from other thumbnails.
Return one coherent generation-ready slot contract. Do not hardcode a generic supplement visual unless it is actually justified by the current title. Keep copy short and mobile-readable. The selected thumbnail text is exact and immutable: preserve it verbatim as the primary headline rather than rewriting it. Other text slots may be concise current-topic context, but must not make stronger health claims than the title.
If a winner slot has no useful current-topic equivalent, use null instead of inventing an unrelated element.
For a full-width top banner, preserve the winner's approximate text density and visual occupancy, not its historical wording. Avoid a sparse 1-2 word banner when the winner banner visibly carries a longer phrase; prefer a concise 4-6 word current-topic/audience phrase when supported by the current title. Do not duplicate the primary headline verbatim in the banner.
For primary_visual and secondary_detail, describe concrete visible current-topic imagery. The secondary detail must relate directly to the primary visual. Do not invent product color, capsule/tablet form, imprint, dosage, brand, label wording, packaging details, or other specifics unless CURRENT_TITLE explicitly supports them. Attention devices must target that secondary detail."""
        schema={
            "type":"object",
            "properties":{
                "top_banner":{"type":["string","null"]},
                "primary_headline":{"type":"string"},
                "boxed_keyword":{"type":["string","null"]},
                "bottom_callout":{"type":["string","null"]},
                "primary_visual":{"type":["string","null"]},
                "secondary_detail":{"type":["string","null"]},
                "attention_target":{"type":["string","null"]},
                "adaptation_rationale":{"type":["string","null"]}
            },
            "required":["top_banner","primary_headline","boxed_keyword","bottom_callout","primary_visual","secondary_detail","attention_target","adaptation_rationale"],
            "additionalProperties":False
        }
        prompt=instruction+"\n\nCURRENT_TITLE: "+str(immutable_title)+"\nSELECTED_THUMBNAIL_TEXT: "+str(selected_text or "")+"\nWINNER_METADATA_JSON:\n"+json.dumps(metadata,ensure_ascii=False)
        payload={
            "model":model,
            "input":[{"role":"user","content":[{"type":"input_text","text":prompt}]}],
            "text":{"format":{"type":"json_schema","name":"current_topic_thumbnail_slots","strict":False,"schema":schema}}
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
        adapted=json.loads(output_text)
        if not isinstance(adapted,dict):
            raise ValueError("Current-topic adapter must return a JSON object.")
        return _sanitize_topic_adaptation(adapted,immutable_title=immutable_title,selected_text=selected_text)
    return adapt

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

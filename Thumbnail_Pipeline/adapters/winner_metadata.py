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
    """Enforce a complete, title-grounded slot contract after AI adaptation."""
    import re
    out=dict(adapted or {})
    title=str(immutable_title or "").strip()
    title_l=title.casefold()
    title_tokens=set(re.findall(r"[a-z0-9]+",title_l))
    headline=str(selected_text or out.get("primary_headline") or "").strip()
    if headline:
        out["primary_headline"]=headline

    blocked_claims=("fix","cure","reverse","secret","eliminate","guaranteed","all you need")
    generic_cta_phrases=("read this","watch this","see this","click here","learn more","what to watch for")
    def unsafe_copy(value: Any) -> bool:
        text=str(value or "")
        return any(re.search(r"\\b"+re.escape(term)+r"\\b",text,flags=re.I) for term in blocked_claims)

    for key in ("top_banner","boxed_keyword","bottom_callout"):
        if unsafe_copy(out.get(key)):
            out[key]=None

    def generic_filler(value: Any) -> bool:
        text=str(value or "").casefold().strip()
        return any(phrase in text for phrase in generic_cta_phrases)

    for key in ("top_banner","bottom_callout"):
        if generic_filler(out.get(key)):
            out[key]=None

    # Preserve winner text-role completeness. Fill missing/fragmentary support slots only
    # from immutable-title semantics; never from historical winner wording.
    # Derive the current topic subject from the immutable title instead of
    # hardcoding a nutrient name. Prefer known supplement/nutrient phrases, then
    # fall back to the noun phrase immediately following WHY YOUR / YOUR.
    known_subjects=(
        "vitamin d3","vitamin d","vitamin b12","vitamin b6","vitamin c","vitamin e",
        "magnesium","calcium","potassium","zinc","iron","creatine","collagen",
        "omega 3","omega-3","fish oil","melatonin","protein",
    )
    subject=None
    for candidate in known_subjects:
        if re.search(r"\\b"+re.escape(candidate)+r"\\b",title_l,re.I):
            subject=candidate.upper()
            break
    if subject is None:
        m=re.search(r"\b(?:why\s+your|your)\s+([a-z0-9][a-z0-9+&' -]{1,40}?)(?=\s+(?:isn['’]?t|is|aren['’]?t|are|doesn['’]?t|does|won['’]?t|will|at|after|before|for|\(|:|\?|$))",title_l,re.I)
        if m:
            candidate=re.sub(r"\\s+"," ",m.group(1)).strip(" -")
            if candidate and len(candidate.split())<=4:
                subject=candidate.upper()
    if subject:
        banner=str(out.get("top_banner") or "").strip()
        # Reject obviously fragmentary banners such as "OVER 60? WHY YOUR MAGNESIUM".
        fragment=bool(re.search(r"\\b(?:why|how|when|what|your|the|a|an)\\s+[A-Z0-9?'-]+$",banner,flags=re.I))
        if fragment:
            out["top_banner"]=None
        if not str(out.get("boxed_keyword") or "").strip():
            out["boxed_keyword"]=subject
        # Support slots are optional: never manufacture filler merely to occupy winner geometry.

        # Copy-slot QA: each support slot must add a distinct idea rather than
        # restating another slot (for example "AT NIGHT" + "AT BEDTIME").
        def copy_tokens(value: Any) -> set[str]:
            stop={"a","an","the","your","you","for","to","of","in","on","at","after","over"}
            return {t for t in re.findall(r"[a-z0-9]+",str(value or "").casefold()) if t not in stop}

        def near_duplicate(a: Any, b: Any) -> bool:
            ta,tb=copy_tokens(a),copy_tokens(b)
            if not ta or not tb:
                return False
            # Normalize the common time-of-day equivalents used by this title.
            # Treat common bedtime wording as the same semantic timing idea.
            # "before bed" tokenizes to "before"+"bed", so normalize both tokens
            # alongside night/nighttime/bedtime to prevent repetitive support copy.
            nightish={"night","nighttime","bedtime","bed","before","sleep","sleeping","asleep","overnight"}
            if ta & nightish: ta=(ta-nightish)|{"night"}
            if tb & nightish: tb=(tb-nightish)|{"night"}
            overlap=len(ta & tb)/max(1,min(len(ta),len(tb)))
            return overlap>=0.75

        banner=out.get("top_banner")
        boxed=out.get("boxed_keyword")
        bottom=out.get("bottom_callout")
        # The boxed keyword intentionally repeats the topic subject; the bottom
        # callout must not repeat banner/headline timing or merely echo the subject.
        if (str(bottom or "").strip()
                and (near_duplicate(bottom,banner)
                     or near_duplicate(bottom,headline)
                     or near_duplicate(bottom,boxed)
                     or len(copy_tokens(bottom))<2)):
            out["bottom_callout"]=None

        # The banner must add a distinct title-grounded idea; audience-only restatements
        # are not useful when the immutable title already supplies that audience.
        banner=out.get("top_banner")
        if str(banner or "").strip():
            audience_only=bool(re.fullmatch(r"(?:for\s+(?:those\s+)?|if\s+you(?:'re|\s+are)\s+|after\s+)?(?:age\s+)?(?:over\s+)?60\+?\??",str(banner).strip(),re.I))
            if audience_only and "60" in title_tokens:
                out["top_banner"]=None
            elif near_duplicate(banner,headline):
                out["top_banner"]=None

    # Nutrient/supplement subject with no explicit dosage form: keep the primary
    # visual grounded, but do not manufacture a duplicate label zoom merely to fill
    # the winner's secondary slot. Secondary/attention slots are capacity, not quota.
    dosage_words={"capsule","capsules","tablet","tablets","pill","pills","softgel","softgels","gummy","gummies","powder","powders"}
    explicit_form=bool(title_tokens & dosage_words)
    if subject and not explicit_form:
        out["primary_visual"]=f"One generic unbranded supplement bottle labeled only '{subject}', positioned in the winner's primary visual zone. No brand, dosage, product color, dosage form, extra props, people, or invented label text."
        secondary=str(out.get("secondary_detail") or "").casefold()
        attention=str(out.get("attention_target") or "").casefold()
        subject_l=subject.casefold()
        duplicate_label_detail=(
            subject_l in secondary
            and any(term in secondary for term in ("label","same bottle","close-up","close up","zoom"))
        )
        if duplicate_label_detail:
            out["secondary_detail"]=None
            out["attention_target"]=None
        elif not str(out.get("secondary_detail") or "").strip():
            out["attention_target"]=None

    # Absolute final copy guard. Never emit blocked claims even if the model
    # generated them after earlier slot logic. Use safe title-grounded fallbacks so
    # winner-required text roles remain populated.
    safe_fallbacks={
        "top_banner": None,
        "boxed_keyword": subject,
        "bottom_callout": None,
    }
    for key in ("top_banner","boxed_keyword","bottom_callout"):
        if unsafe_copy(out.get(key)):
            out[key]=safe_fallbacks.get(key)
    for key in ("top_banner","bottom_callout"):
        if generic_filler(out.get(key)):
            out[key]=None
    return out

def openai_current_topic_adapter(api_key: str, *, model: str = "gpt-5-mini", timeout: int = 90):
    """Adapt winner composition slots to the current immutable title without mixing references."""
    key=str(api_key or "").strip()
    if not key:
        raise ValueError("OpenAI API key is required for current-topic adaptation.")

    def adapt(*, metadata: dict[str, Any], immutable_title: str, selected_text: str | None, script_support: dict[str, Any] | None = None) -> dict[str, Any]:
        instruction="""You are adapting a proven YouTube thumbnail composition to ONE current video topic.
FIRST build a joint semantic coverage plan before writing any slots. Extract atomic CURRENT_TITLE tokens: subject, audience, number/payload, tension/problem, timing/context, and differentiator when explicitly present. Treat the historical winner's text positions as a CAPACITY CEILING, never a quota.
Evaluate the ENTIRE text+visual contract together, not each slot independently. Each semantic token should have one best carrier (headline, banner, box, callout, primary visual, secondary visual). Repeating a token is allowed only when it adds clear marginal information; otherwise use null. Account for the always-visible YouTube title and for information already obvious in the image.
Use this internal coverage scoreboard for every candidate: token -> best carrier -> emphasis level -> already covered by title? -> already covered by image? -> redundancy flags -> claim-safe? -> final assignment. Do not output the scoreboard; use it to choose the coherent final contract.
Use the supplied winner metadata ONLY for reusable visual structure, geometry, hierarchy, palette, typography roles, and attention-device roles.
Use CURRENT_TITLE and SELECTED_THUMBNAIL_TEXT only within the limits of SCRIPT_SUPPORT_JSON. The final script is the semantic ceiling: every emitted text idea, primary visual, secondary visual, and attention target must be supported by SCRIPT_SUPPORT_JSON. If a title idea is not script-supported, do not use it in an optional slot or visual. Never carry historical winner topic words or objects into the adapted content.
Do not use or combine subjects from other thumbnails.
Return one coherent generation-ready slot contract. Do not hardcode a generic supplement visual unless it is actually justified by the current title. Keep copy short and mobile-readable. The selected thumbnail text is exact and immutable: preserve it verbatim as the primary headline rather than rewriting it. Other text slots may be concise current-topic context, but must not make stronger health claims than the title.
Before filling text slots, extract CURRENT_TITLE semantics into distinct ideas such as audience, subject, tension/problem, timing/number hook, and any explicitly stated consequence. Assign each emitted slot a distinct communicative job. Do not fill a slot merely because the historical winner had text there.
Treat winner metadata as geometry/style, not as a mandate to preserve the historical semantic purpose of a slot. The top banner and bottom callout are optional. Emit null when they would only repeat the title, repeat another thumbnail slot, use a generic CTA/filler phrase, or add an unsupported idea.
Do not use generic filler such as READ THIS, WATCH THIS, SEE THIS, LEARN MORE, or WHAT TO WATCH FOR.
Do not paraphrase an audience marker already explicit in CURRENT_TITLE merely to occupy the banner (for example FOR THOSE OVER 60 when the title already says Over 60).
The banner, when used, should carry a distinct title-grounded tension/context idea. The bottom callout, when used, should add another distinct title-grounded dimension. Never invent numbered-item facts (for example #2 IS COMMON) or stronger outcomes not stated in CURRENT_TITLE.
Preserve the winner's geometry, hierarchy, and styling for whichever slots are actually useful; optional null text slots may remain empty rather than being filled with weak copy.
For primary_visual and secondary_detail, describe concrete visible current-topic imagery. The primary visual should carry the strongest concrete title-grounded token. A secondary detail is OPTIONAL and must express a DIFFERENT title-grounded semantic token than the primary visual; a zoom or repeated label that merely restates the primary subject is not useful. If no distinct honest secondary visual exists without invention, return null for secondary_detail and attention_target. Attention devices are permitted only when they point to a unique informative secondary referent. Do not invent product color, capsule/tablet form, imprint, dosage, brand, label wording, packaging details, medical effects, or unrelated props unless CURRENT_TITLE explicitly supports them."""
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
        prompt=instruction+"\n\nCURRENT_TITLE: "+str(immutable_title)+"\nSELECTED_THUMBNAIL_TEXT: "+str(selected_text or "")+"\nSCRIPT_SUPPORT_JSON:\n"+json.dumps(script_support or {},ensure_ascii=False)+"\nWINNER_METADATA_JSON:\n"+json.dumps(metadata,ensure_ascii=False)
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

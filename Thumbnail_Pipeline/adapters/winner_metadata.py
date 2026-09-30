from __future__ import annotations

import base64
import json
import socket
import time
import urllib.error
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
        instruction="""Inspect ONLY the supplied winning YouTube thumbnail pixels. Produce detailed reusable thumbnail metadata as JSON. Do not infer visual facts from the video title, CTR, topic, or other thumbnails. Describe what is visibly present, including exact visible text when readable, canvas/background, full composition, text/visual split, banners, text zones, primary/secondary visuals, presenter/human presence, arrows/circles/boxes/highlights, typography, colors, visual hierarchy, semantic hook structure supported by visible copy, approximate percentage geometry, density, thumbnail patterns, and a reusable_composition_contract. The reusable contract must preserve composition/style roles while clearly separating topic-specific objects/words from reusable structure.
CRITICAL TEXT-RELATIONSHIP ANALYSIS: analyze the visible copy as a reading sequence, not merely independent boxes. In semantic_structure explicitly record whether adjacent text bands form one progressive/continuous hook or sentence, independent messages, headline-plus-CTA, or another visibly supported relationship; include reading order, how each band continues/completes the prior band, and whether the final band is a conclusion/action to that same hook. In reusable_composition_contract preserve this text-flow relationship as a reusable semantic-composition pattern, while treating the historical words themselves as topic-specific. Do NOT convert each historical band into an obligation to invent a different idea. A future adaptation may collapse/null a band if the current-topic message cannot preserve the same coherent reading flow without redundancy.
STRUCTURAL CONTRACT IS REQUIRED. Create structural_contract.bands[] from the actual visible text panels/bands in reading order. Each band needs stable band_id, numeric x_pct/y_pct/w_pct/h_pct, hierarchy_rank, wrap_policy='inside_band_only', measured rotation_deg and measured glyph slant_deg, alignment, and style_role. Create structural_contract.roles[] for reusable visual roles (presenter, support/chair, target, attention_device, environment) with numeric boxes and optional attention_target_role_id. Historical words, anatomy, products, and topic instances belong only in historical_annotations; they are not reusable requirements. Derive complexity_budget from what is visibly present: exact text_band_count plus ceilings for people, informational objects, and attention devices. Never invent an element that is not visible. Use null/unknown only outside required numeric structural fields; estimate visible percentages conservatively. Font slant must be based on pixels only. Return one JSON object only."""
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
                "reusable_composition_contract":{"type":"object","additionalProperties":True},
                "structural_contract":{
                    "type":"object",
                    "properties":{
                        "bands":{"type":"array","items":{"type":"object","properties":{
                            "band_id":{"type":"string"},"reading_order":{"type":"integer"},
                            "x_pct":{"type":"number"},"y_pct":{"type":"number"},"w_pct":{"type":"number"},"h_pct":{"type":"number"},
                            "hierarchy_rank":{"type":"integer"},"wrap_policy":{"type":"string"},
                            "rotation_deg":{"type":"number"},"slant_deg":{"type":"number"},
                            "alignment":{"type":["string","null"]},"style_role":{"type":["string","null"]}
                        },"required":["band_id","reading_order","x_pct","y_pct","w_pct","h_pct","hierarchy_rank","wrap_policy","rotation_deg","slant_deg","alignment","style_role"],"additionalProperties":False}},
                        "roles":{"type":"array","items":{"type":"object","properties":{
                            "role_id":{"type":"string"},"role_type":{"type":"string"},"required":{"type":"boolean"},
                            "x_pct":{"type":"number"},"y_pct":{"type":"number"},"w_pct":{"type":"number"},"h_pct":{"type":"number"},
                            "saliency_rank":{"type":"integer"},"attention_target_role_id":{"type":["string","null"]}
                        },"required":["role_id","role_type","required","x_pct","y_pct","w_pct","h_pct","saliency_rank","attention_target_role_id"],"additionalProperties":False}},
                        "complexity_budget":{"type":"object","properties":{
                            "text_band_count":{"type":"integer"},"max_people":{"type":"integer"},
                            "max_informational_objects":{"type":"integer"},"max_attention_devices":{"type":"integer"}
                        },"required":["text_band_count","max_people","max_informational_objects","max_attention_devices"],"additionalProperties":False},
                        "historical_annotations":{"type":"object","additionalProperties":True}
                    },
                    "required":["bands","roles","complexity_budget","historical_annotations"],"additionalProperties":False
                }
            },
            "required":["asset_type","content_category","topic","visual_style","canvas","composition","text","color_system","primary_visual","secondary_visual","attention_devices","visual_hierarchy","semantic_structure","layout_geometry","design_density","thumbnail_pattern","reusable_composition_contract","structural_contract"],
            "additionalProperties":False
        }
        payload={
            "model":model,
            "input":[{"role":"user","content":[{"type":"input_text","text":instruction},{"type":"input_image","image_url":data_url}]}],
            "text":{"format":{"type":"json_schema","name":"winner_thumbnail_metadata","strict":False,"schema":metadata_schema}}
        }
        request_data=json.dumps(payload).encode("utf-8")
        request_headers={"Authorization":f"Bearer {key}","Content-Type":"application/json","User-Agent":"SeniorHealthAI-ThumbnailPipeline/1.0"}
        body=None
        last_error=None
        # Vision metadata can occasionally exceed the normal response read timeout.
        # Retry transient network/read failures only; never reuse stale metadata.
        for attempt in range(1,4):
            req=urllib.request.Request("https://api.openai.com/v1/responses",data=request_data,headers=request_headers,method="POST")
            try:
                with urllib.request.urlopen(req,timeout=max(timeout,180)) as response:
                    body=json.loads(response.read().decode("utf-8"))
                break
            except (TimeoutError,socket.timeout,ConnectionError,urllib.error.URLError) as exc:
                last_error=exc
                if attempt>=3:
                    raise RuntimeError(f"Fresh winner metadata analysis failed after {attempt} attempts: {exc}") from exc
                time.sleep(attempt*2)
        if body is None:
            raise RuntimeError(f"Fresh winner metadata analysis failed: {last_error}")
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
    selected=str(selected_text or "").strip()
    headline=str(out.get("primary_headline") or "").strip()
    # The selected copy is immutable in wording/presence, NOT in physical band.
    # The adapter may place it in any visible text slot required by the winner's
    # reading flow. Restore it only if the model accidentally omitted it entirely.
    text_slot_keys=("top_banner","primary_headline","boxed_keyword","bottom_callout")
    if selected:
        present=any(str(out.get(k) or "").strip().casefold()==selected.casefold() for k in text_slot_keys)
        if not present:
            out["primary_headline"]=selected
            headline=selected

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

    # Nutrient/supplement subject with no explicit dosage form: ground the object
    # without fighting a winner-defined presenter anchor. A presenter-led winner keeps
    # the human as primary; the current-topic object occupies the detail/target role.
    dosage_words={"capsule","capsules","tablet","tablets","pill","pills","softgel","softgels","gummy","gummies","powder","powders"}
    explicit_form=bool(title_tokens & dosage_words)
    if subject and not explicit_form:
        meta_text=str(out.get("_winner_metadata_text") or "").casefold()
        presenter_anchor=bool(out.get("_winner_presenter_anchor"))
        object_desc=f"One generic unbranded supplement bottle labeled only '{subject}', with no brand, dosage, product color, dosage form, or invented label text."
        if presenter_anchor:
            out["primary_visual"]="Neutral presenter in the winner-defined presenter zone, preserving the winner's photographic human anchor and directing attention toward the current-topic target without implying a medical outcome."
            if not str(out.get("secondary_detail") or "").strip():
                out["secondary_detail"]=object_desc
            if not str(out.get("attention_target") or "").strip():
                out["attention_target"]=f"The generic unbranded '{subject}' bottle; presenter gesture and winner-defined attention devices point to this same object."
        else:
            out["primary_visual"]=object_desc+" Positioned in the winner's primary visual zone."
            secondary=str(out.get("secondary_detail") or "").casefold()
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

    def adapt(*, metadata: dict[str, Any], immutable_title: str, selected_text: str | None, script_support: dict[str, Any] | None = None, revision_feedback: dict[str, Any] | None = None, prior_contract: dict[str, Any] | None = None) -> dict[str, Any]:
        instruction="""You are adapting a proven YouTube thumbnail composition to ONE current video topic.
FIRST build a joint semantic coverage plan before writing any slots. Extract atomic CURRENT_TITLE tokens: subject, audience, number/payload, tension/problem, timing/context, and differentiator when explicitly present. Treat the historical winner's text positions as a CAPACITY CEILING, never a quota.
Evaluate the ENTIRE text+visual contract together, not each slot independently. Each semantic token should have one best carrier (headline, banner, box, callout, primary visual, secondary visual). Repeating a token is allowed only when it adds clear marginal information; otherwise use null. Account for the always-visible YouTube title and for information already obvious in the image.
PRESERVE WINNER TEXT-FLOW LOGIC, NOT JUST TEXT-BOX GEOMETRY. Read WINNER_METADATA semantic_structure and reusable_composition_contract to determine whether the historical bands form one progressive/continuous hook, independent messages, or headline-plus-CTA. If the winner uses a progressive hook, the adapted visible text bands must read naturally in order as one coherent current-topic message. Do not populate those bands with unrelated facts merely because separate slots exist. The exact SELECTED_THUMBNAIL_TEXT remains immutable; use optional surrounding bands only when they naturally extend or complete that same hook without duplicating it. If coherent continuation is impossible, collapse/null optional bands rather than producing a fragmented multi-message thumbnail.
Use this internal coverage scoreboard for every candidate: token -> best carrier -> emphasis level -> already covered by title? -> already covered by image? -> redundancy flags -> claim-safe? -> final assignment. Do not output the scoreboard; use it to choose the coherent final contract.
Use the supplied winner metadata ONLY for reusable visual structure, geometry, hierarchy, palette, typography roles, and attention-device roles.
PRESERVE WINNER VISUAL ROLE TYPES. If WINNER_METADATA defines a presenter/person/portrait as a primary or anchor role, the adapted contract MUST retain a neutral presenter/person/portrait in that same role and zone. Do not replace that human anchor with the current-topic object. Instead, map the strongest script-supported current-topic object to the winner's target/detail/object role and let the presenter support the existing attention flow (for example, looking or pointing toward that object) only when that neutral gesture adds no unsupported health claim. Likewise, if the winner's primary role is object-led with no presenter, do not invent a presenter. Historical topic-specific anatomy, props, symptoms, or objects are never preserved merely because the visual role is preserved.
On repair passes, treat a utility-gate finding that says a winner presenter/person anchor was removed as mandatory: restore the neutral human anchor in primary_visual and move the script-supported topic object to secondary_detail/attention_target as appropriate. Do not repeat the failed object-only primary_visual.
Use CURRENT_TITLE and SELECTED_THUMBNAIL_TEXT only within the limits of SCRIPT_SUPPORT_JSON. The final script is the semantic ceiling: every emitted text idea, primary visual, secondary visual, and attention target must be supported by SCRIPT_SUPPORT_JSON. If a title idea is not script-supported, do not use it in an optional slot or visual. Never carry historical winner topic words or objects into the adapted content.
Do not use or combine subjects from other thumbnails.
Return one coherent generation-ready slot contract. Do not hardcode a generic supplement visual unless it is actually justified by the current title. Keep copy short and mobile-readable. The selected thumbnail text is exact and immutable in WORDING AND PRESENCE, but NOT in physical text-band/slot. It must appear verbatim exactly once somewhere among top_banner, primary_headline, boxed_keyword, or bottom_callout. Choose its slot from the winner's reading flow; do not force it into primary_headline when that breaks the progressive hook. Other text slots may be concise current-topic context, but must not make stronger health claims than the title.
Before filling text slots, extract CURRENT_TITLE semantics into distinct ideas such as audience, subject, tension/problem, timing/number hook, and any explicitly stated consequence. Assign each emitted slot a distinct communicative job. Do not fill a slot merely because the historical winner had text there.
Treat winner metadata as geometry/style, not as a mandate to preserve the historical semantic purpose of a slot. The top banner and bottom callout are optional. Emit null when they would only repeat the title, repeat another thumbnail slot, use a generic CTA/filler phrase, or add an unsupported idea.
Do not use generic filler such as READ THIS, WATCH THIS, SEE THIS, LEARN MORE, or WHAT TO WATCH FOR.
Do not paraphrase an audience marker already explicit in CURRENT_TITLE merely to occupy the banner (for example FOR THOSE OVER 60 when the title already says Over 60).
The banner, when used, should carry a distinct title-grounded tension/context idea. The bottom callout, when used, should add another distinct title-grounded dimension. Never invent numbered-item facts (for example #2 IS COMMON) or stronger outcomes not stated in CURRENT_TITLE.
Preserve the winner's geometry, hierarchy, and styling for whichever slots are actually useful; optional null text slots may remain empty rather than being filled with weak copy.
For primary_visual and secondary_detail, describe concrete visible current-topic imagery. The primary visual should carry the strongest concrete title-grounded token. A secondary detail is OPTIONAL and must express a DIFFERENT title-grounded semantic token than the primary visual; a zoom or repeated label that merely restates the primary subject is not useful. If no distinct honest secondary visual exists without invention, return null for secondary_detail and attention_target. Attention devices are permitted only when they point to a unique informative secondary referent. Do not invent product color, capsule/tablet form, imprint, dosage, brand, label wording, packaging details, medical effects, or unrelated props unless CURRENT_TITLE explicitly supports them.
When REVISION_FEEDBACK_JSON is non-empty, this is a repair pass. Fix every actionable finding while preserving already-valid slots where possible. Do not weaken script grounding, rewrite the immutable headline, or invent content merely to satisfy a finding. PRIOR_CONTRACT_JSON is the failed contract to repair, not a new reference source.
REPAIR INVARIANT: after every repair, compare all non-null text slots (top_banner, primary_headline, boxed_keyword, bottom_callout) case-insensitively. Never return the same visible phrase in more than one slot. SELECTED_THUMBNAIL_TEXT must remain verbatim exactly once, but may move between these slots to satisfy the winner reading sequence. If a repair would duplicate an existing phrase, keep the stronger carrier and set the weaker optional slot to null unless a distinct script-supported phrase adds real marginal information.
REPAIR INVARIANT: preserve presenter -> attention -> target as a structural relationship, but never restore the historical winner's topic-specific body part/object merely to satisfy geometry. The target may be remapped to one unique current-topic object supported by SCRIPT_SUPPORT_JSON, and presenter gesture plus attention device must point to that same target.
STRUCTURED VISUAL PLACEMENTS ARE MANDATORY. Populate visual_placements[] as the executable visual contract, not a prose summary. Every visible person, informational object, attention device, support/chair, or environment role that the generation should render must be one placement bound to an existing WINNER_METADATA structural_contract.roles[].role_id. TEXT ROLES ARE EXCLUDED: role_type text_stack, text, text_band, or typography must never receive a visual_placement of any kind; visible text is governed solely by TEXT BANDS JSON. Never invent a role_id. Script-supported visual concepts are candidates, not a checklist: discard candidates that do not fit an available winner role or budget. Exactly one informational_object must have is_primary_target=true. Presenter/person is kind=person and consumes the people budget, never the informational-object budget. Chair/support and environment are non-informational. Attention devices use kind=attention_device and attention_target_role_id must equal the primary target's role_id. Do not hide multiple informational objects inside one placement description: one visible informational object = one placement. ENVIRONMENT IS ATMOSPHERE ONLY: an environment placement may describe room/background qualities such as lighting, wall, floor, or non-salient ambience, but must not contain or name independent props, products, containers, books/notebooks/diaries, labels, cards, food/drink, devices, or other countable informational objects. SUPPORT IS STRUCTURE ONLY: a support placement may describe only the winner-equivalent structural support (for example chair/table surface when that support role exists) and must not smuggle informational props into its description. Every independent prop must be its own kind=informational_object placement bound to a compatible winner role; if no such role exists, discard it. If only one target role is available, choose the single strongest current-topic target and discard prescription bottles, antacids, laxatives, diaries, labels, or other supported candidates rather than clustering or hiding them in target, support, or environment prose."""
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
                "visual_placements":{"type":"array","items":{"type":"object","properties":{
                    "placement_id":{"type":"string"},
                    "role_id":{"type":"string"},
                    "kind":{"type":"string","enum":["person","informational_object","attention_device","support","environment"]},
                    "description":{"type":"string"},
                    "is_primary_target":{"type":"boolean"},
                    "attention_target_role_id":{"type":["string","null"]}
                },"required":["placement_id","role_id","kind","description","is_primary_target","attention_target_role_id"],"additionalProperties":False}},
                "adaptation_rationale":{"type":["string","null"]}
            },
            "required":["top_banner","primary_headline","boxed_keyword","bottom_callout","primary_visual","secondary_detail","attention_target","visual_placements","adaptation_rationale"],
            "additionalProperties":False
        }
        prompt=instruction+"\n\nCURRENT_TITLE: "+str(immutable_title)+"\nSELECTED_THUMBNAIL_TEXT: "+str(selected_text or "")+"\nSCRIPT_SUPPORT_JSON:\n"+json.dumps(script_support or {},ensure_ascii=False)+"\nWINNER_METADATA_JSON:\n"+json.dumps(metadata,ensure_ascii=False)+"\nPRIOR_CONTRACT_JSON:\n"+json.dumps(prior_contract or {},ensure_ascii=False)+"\nREVISION_FEEDBACK_JSON:\n"+json.dumps(revision_feedback or {},ensure_ascii=False)
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
        meta_text=json.dumps(metadata,ensure_ascii=False).casefold()
        presenter_anchor=any(token in meta_text for token in (
            '"presenter"', '"presenter_', '"person"', '"person_', '"portrait"',
            '"human"', '"human_', '"man"', '"male"', "presenter anchor",
            "photographic presenter", "presenter-led", "presenter_led"
        )) and not any(token in meta_text for token in (
            '"presenter_present": false', '"presenter_present":false',
            '"human_present": false', '"human_present":false'
        ))
        adapted["_winner_presenter_anchor"]=presenter_anchor
        adapted["_winner_metadata_text"]=meta_text
        sanitized=_sanitize_topic_adaptation(adapted,immutable_title=immutable_title,selected_text=selected_text)
        sanitized.pop("_winner_presenter_anchor",None)
        sanitized.pop("_winner_metadata_text",None)
        # A presenter/person anchor is a reusable composition role, not historical topic
        # content. If the model drops that proven role, deterministically restore a neutral
        # anchor and keep current-topic objects in detail/target roles.
        if presenter_anchor:
            primary=str(sanitized.get("primary_visual") or "").casefold()
            has_human=any(token in primary for token in ("presenter","person","man","woman","older adult","senior"))
            if not has_human:
                original_primary=sanitized.get("primary_visual")
                sanitized["primary_visual"]="Neutral presenter in the winner-defined presenter zone, preserving the winner's photographic human anchor and directing visual attention toward the current-topic target without implying a medical outcome."
                if original_primary and not sanitized.get("secondary_detail"):
                    sanitized["secondary_detail"]=original_primary
                if original_primary and not sanitized.get("attention_target"):
                    sanitized["attention_target"]=original_primary
        # Hard postcondition: immutable selected copy is wording/presence locked, not
        # slot locked. Sanitization must never accidentally erase it. Preserve the model's
        # chosen band when present; if absent, restore once as a temporary primary carrier
        # so the utility repair pass can move it to the winner-correct band.
        selected=str(selected_text or "").strip()
        text_slots=("top_banner","primary_headline","boxed_keyword","bottom_callout")
        if selected:
            matches=[k for k in text_slots if str(sanitized.get(k) or "").strip().casefold()==selected.casefold()]
            if not matches:
                sanitized["primary_headline"]=selected
            elif len(matches)>1:
                for k in matches[1:]:
                    sanitized[k]=None
        # adaptation_rationale is internal diagnostic output, never part of the generation contract.
        sanitized.pop("adaptation_rationale",None)
        return sanitized
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

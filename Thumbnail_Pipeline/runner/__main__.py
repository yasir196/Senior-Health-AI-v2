from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from typing import Any

from Thumbnail_Pipeline.concept_engine import build_concept_direction
from Thumbnail_Pipeline.composition import build_composition_spec
from Thumbnail_Pipeline.qa import apply_composition_review, evaluate_generation_gate
from Thumbnail_Pipeline.prompt_export import export_final_thumbnail_prompt
from Thumbnail_Pipeline.adapters.v2_analytics_db import V2AnalyticsReadOnlyAdapter
from Thumbnail_Pipeline.intelligence.title_clusters import discover_title_clusters, assign_title_cluster
from Thumbnail_Pipeline.db.cluster_store import persist_title_clusters
from Thumbnail_Pipeline.intelligence.cluster_prior import eligible_cluster_winners
from Thumbnail_Pipeline.intelligence.text_mechanisms import discover_text_mechanisms, transformation_text_candidates, constraint_text_candidates, recurrent_observed_text_candidates, filter_incomplete_title_prefix_candidates
from Thumbnail_Pipeline.adapters.youtube_reference import collect_references
from Thumbnail_Pipeline.adapters.youtube_thumbnail_analysis import analyze_youtube_reference_thumbnails, openai_thumbnail_text_analyzer, clear_youtube_reference_thumbnails
from Thumbnail_Pipeline.adapters.v2_youtube_api import V2YouTubeReferenceProvider, access_token_from_v2_files_read_only, discover_v2_youtube_oauth_files_read_only
from Thumbnail_Pipeline.adapters.winner_metadata import build_fresh_winner_metadata, openai_winner_metadata_analyzer, openai_current_topic_adapter
from Thumbnail_Pipeline.qa.contract_qa import build_render_structure, evaluate_contract_qa

def resolve_project(project: str, root: str = "Projects") -> Path:
    base = Path(root).resolve()
    candidate = (base / project).resolve()
    if candidate.parent != base:
        raise ValueError("Project must be a direct child of Projects/.")
    if not candidate.is_dir():
        raise FileNotFoundError(f"Project folder not found: {candidate}")
    return candidate

def _read_project_json(project: Path) -> dict[str, Any]:
    path=project/"project.json"
    if not path.is_file():
        raise FileNotFoundError(f"Required project metadata not found: {path}")
    data=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data,dict):
        raise ValueError("project.json must contain a JSON object.")
    return data

def _title(meta: dict[str, Any]) -> str:
    for key in ("title","video_title","anchor_title","outlier_title"):
        value=meta.get(key)
        if isinstance(value,str) and value.strip():
            return value.strip()
    raise ValueError("No immutable project title found in project.json (title/video_title/anchor_title/outlier_title).")

def _rank_visible_subjects(subjects: list[str], title: str) -> list[str]:
    """Deduplicate visible subjects and rank topic-specific descriptions first."""
    import re
    title_tokens={x for x in re.findall(r"[a-z0-9]+",title.lower()) if len(x)>2}
    # Channel presentation contract: external references may visibly contain clinicians,
    # but those styling cues must never become final visual-subject suggestions.
    blocked_presenter_cues=("doctor","clinician","physician","stethoscope","white coat","lab coat","scrubs","surgical scrubs")
    seen=set(); ranked=[]
    for i,raw in enumerate(subjects):
        value=" ".join(str(raw or "").split()).strip()
        key=value.casefold()
        if not value or key in seen: continue
        if any(cue in key for cue in blocked_presenter_cues):
            continue
        seen.add(key)
        tokens=set(re.findall(r"[a-z0-9]+",key))
        overlap=len(tokens & title_tokens)
        # Keep the original visible phrase, but reject mixed-object descriptions when
        # topic evidence is diluted by unsupported content nouns (e.g. blood vessel).
        stop={"with","above","over","under","beside","near","holding","held","hand","hands",
              "man","woman","person","cup","mug","glass","white","black","small","large"}
        content={x for x in tokens if len(x)>2 and x not in stop}
        unsupported=content-title_tokens
        if overlap and unsupported:
            continue
        specificity=sum(1 for x in tokens if len(x)>=5)
        ranked.append((overlap,specificity,len(tokens),-i,value))
    ranked.sort(reverse=True)
    return [x[-1] for x in ranked]

def _coherent_youtube_composition_votes(rows: list[dict[str, Any]]) -> tuple[list[str], list[str], int]:
    """Use only internally consistent visual composition classifications.

    A structural layout already implies the text side. If the same thumbnail's
    text-placement label contradicts that layout, treat that observation as noisy
    rather than allowing it to dilute both recurrence votes.
    """
    implied={
        "text_left_subject_right":"left",
        "subject_left_text_right":"right",
        "text_top_subject_bottom":"center",
        "subject_top_text_bottom":"center",
        "centered_subject":"center",
    }
    placements=[]; layouts=[]; conflicts=0
    for row in rows:
        placement=row.get("external_thumbnail_text_placement")
        layout=row.get("external_thumbnail_structural_layout")
        placement=placement if placement in ("left","center","right") else None
        layout=layout if layout in implied else None
        if placement and layout and placement != implied[layout]:
            conflicts+=1
            continue
        if placement:
            placements.append(str(placement))
        if layout:
            layouts.append(str(layout))
    return placements,layouts,conflicts

def _layout_family(value: Any) -> str | None:
    """Normalize DB free-text layouts and YouTube structural labels to comparable families."""
    s=" ".join(str(value or "").lower().replace("_"," ").split())
    if not s:
        return None
    # Vertical geometry must be recognized before generic left/right words; DB prose
    # can mention "presenter left" while the actual dominant structure is text-above/visual-below.
    if "text top subject bottom" in s:
        return "text_top_subject_bottom"
    if "subject top text bottom" in s:
        return "subject_top_text_bottom"
    if "text" in s and ("upper center" in s or "upper-center" in s) and any(x in s for x in ("lower center","lower-center","lower right","lower-right")):
        return "text_top_subject_bottom"
    if "text left subject right" in s or ("text" in s and "left" in s and any(x in s for x in ("presenter on the right","jar on the right","spoon are on the right","subject right"))):
        return "text_left_subject_right"
    if "subject left text right" in s or ("presenter" in s and "left" in s and "text" in s and "right" in s):
        return "subject_left_text_right"
    if "centered subject" in s:
        return "centered_subject"
    return None

def _layout_positions(value: Any, family: str | None = None) -> tuple[str | None, str | None]:
    """Infer prompt placement fields from the selected evidence-backed layout."""
    s=" ".join(str(value or "").lower().replace("_"," ").split())
    fam=family or _layout_family(value)
    text=None; subject=None
    if fam=="text_left_subject_right":
        text,subject="left","right"
    elif fam=="subject_left_text_right":
        text,subject="right","left"
    elif fam=="text_top_subject_bottom":
        text,subject="center","bottom"
    elif fam=="subject_top_text_bottom":
        text,subject="center","top"
    elif fam=="centered_subject":
        text,subject="center","center"
    # Preserve more specific presenter evidence when the DB description supplies it.
    if "presenter on the left" in s or "presenter left" in s:
        subject="left"
    elif "presenter on the right" in s or "presenter right" in s:
        subject="right"
    return text,subject

def _zone_from_phrase(text: str, role: str) -> str | None:
    """Extract a generic visual zone from historical free-text layout evidence."""
    import re
    s=" ".join(str(text or "").lower().replace("_"," ").replace("-"," ").split())
    if not s:
        return None
    role_patterns={
        "text": r"(?:text|copy|headline)",
        "presenter": r"(?:presenter|host|man|woman|person|face)",
        "primary": r"(?:jar|cup|coffee|feet|foot|spoon|object|product|setup|visual|subject)",
        "secondary": r"(?:secondary|detail|badge|accent|spoon|arrow)",
    }
    role_re=role_patterns[role]
    zones=[
        ("upper-left",r"(?:upper|top) left"),("upper-center",r"(?:upper|top) center"),
        ("upper-right",r"(?:upper|top) right"),("lower-left",r"(?:lower|bottom) left"),
        ("lower-center",r"(?:lower|bottom) center"),("lower-right",r"(?:lower|bottom) right"),
        ("center-left",r"(?:center left|left center)"),("center-right",r"(?:center right|right center)"),
        ("center",r"center"),("left",r"left"),("right",r"right"),
    ]
    clauses=[x.strip() for x in re.split(r"[,;]",s) if x.strip()]
    for clause in clauses:
        if not re.search(role_re,clause):
            continue
        for zone,pat in zones:
            if re.search(pat,clause):
                if zone=="left": return "center-left"
                if zone=="right": return "center-right"
                return zone
    return None

def _db_structural_signature(raw: Any) -> dict[str, str | None]:
    s=str(raw or "")
    return {
        "text_zone":_zone_from_phrase(s,"text"),
        "primary_visual_zone":_zone_from_phrase(s,"primary"),
        "presenter_zone":_zone_from_phrase(s,"presenter"),
        "secondary_visual_zone":_zone_from_phrase(s,"secondary"),
    }

def _zone_side(zone: Any) -> str | None:
    z=str(zone or "").lower()
    if z in {"none","unknown",""}: return None
    if "left" in z: return "left"
    if "right" in z: return "right"
    if "center" in z: return "center"
    return None

def _signatures_compatible(db_sig: dict[str, Any], yt_sig: Any) -> bool:
    """Require compatible visual roles when detailed YouTube geometry is available."""
    if not isinstance(yt_sig,dict):
        return True
    compared=0
    for key in ("text_zone","primary_visual_zone","presenter_zone"):
        expected=db_sig.get(key)
        observed=yt_sig.get(key)
        if not expected or str(observed or "").lower() in {"","unknown","none"}:
            continue
        compared+=1
        if _zone_side(expected) != _zone_side(observed):
            return False
    return compared>0

def _select_data_driven_layout(winners: list[dict[str, Any]], youtube_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Try fresh DB winners in evidence order, then fall back to highest-view YouTube layout."""
    yt_valid=[]
    for row in youtube_rows:
        layout=row.get("external_thumbnail_structural_layout")
        family=_layout_family(layout)
        if not family:
            continue
        try:
            views=int(row.get("views") or 0)
        except (TypeError,ValueError):
            views=0
        yt_valid.append((views,family,row))
    # Try every DB winner independently in evidence order. A coarse layout family is
    # only the current-topic validation requirement; detailed geometry is a preference,
    # not a veto, because the DB winner itself is the reusable composition authority.
    for winner in winners:
        raw=winner.get("composition_layout")
        family=_layout_family(raw)
        if not family:
            continue
        db_signature=_db_structural_signature(raw)
        family_matches=[x for x in yt_valid if x[1]==family]
        if family_matches:
            compatible=[
                x for x in family_matches
                if _signatures_compatible(db_signature,x[2].get("external_thumbnail_structural_signature"))
            ]
            matches=compatible or family_matches
            matches.sort(key=lambda x:x[0],reverse=True)
            text_pos,subject_pos=_layout_positions(raw,family)
            return {"source":"db_winner_validated_on_youtube","layout":family,"family":family,
                    "historical_layout_evidence":raw,
                    "text_placement":text_pos,"subject_placement":subject_pos,
                    "winner_title":winner.get("title"),"winner_ctr":winner.get("ctr"),
                    "winner_impressions":winner.get("impressions"),
                    "winner_video_id":winner.get("youtube_video_id"),
                    "winner_video_url":f"https://www.youtube.com/watch?v={winner.get('youtube_video_id')}" if winner.get("youtube_video_id") else None,
                    "winner_presenter_present":winner.get("presenter_present"),
                    "winner_visual_strategy":"presenter_led" if bool(winner.get("presenter_present")) else "object_led",
                    "structural_signature":db_signature,
                    "youtube_match_structural_signature":matches[0][2].get("external_thumbnail_structural_signature"),
                    "youtube_match_video_id":matches[0][2].get("video_id"),
                    "youtube_match_views":matches[0][0]}
    if yt_valid:
        yt_valid.sort(key=lambda x:x[0],reverse=True)
        views,family,row=yt_valid[0]
        text_pos,subject_pos=_layout_positions(row.get("external_thumbnail_structural_layout"),family)
        return {"source":"youtube_highest_view_fallback","layout":row.get("external_thumbnail_structural_layout"),
                "family":family,"text_placement":text_pos,"subject_placement":subject_pos,
                "youtube_match_video_id":row.get("video_id"),"youtube_match_views":views}
    # Offline/no-analyzable-YouTube fallback: retain the strongest fresh DB winner rather
    # than inventing a layout or invoking a consensus rule.
    for winner in winners:
        raw=winner.get("composition_layout"); family=_layout_family(raw)
        if family:
            text_pos,subject_pos=_layout_positions(raw,family)
            return {"source":"db_winner_youtube_unavailable","layout":family,"family":family,
                    "historical_layout_evidence":raw,
                    "text_placement":text_pos,"subject_placement":subject_pos,
                    "winner_title":winner.get("title"),"winner_ctr":winner.get("ctr"),
                    "winner_impressions":winner.get("impressions"),
                    "winner_video_id":winner.get("youtube_video_id"),
                    "winner_video_url":f"https://www.youtube.com/watch?v={winner.get('youtube_video_id')}" if winner.get("youtube_video_id") else None,
                    "winner_presenter_present":winner.get("presenter_present"),
                    "winner_visual_strategy":"presenter_led" if bool(winner.get("presenter_present")) else "object_led"}
    return None

def build_project_prompt_state(project: Path, analytics_db: Path | None = None, cluster_db: Path | None = None, youtube_provider=None, youtube_text_analyzer=None) -> dict[str, Any]:
    meta=_read_project_json(project); title=_title(meta)
    adapter=V2AnalyticsReadOnlyAdapter(analytics_db) if analytics_db else None
    historical=adapter.to_intelligence_rows() if adapter else []
    if historical:
        discovered=discover_title_clusters(historical)
    else:
        from Thumbnail_Pipeline.intelligence.settings import load_settings
        cluster_cfg=load_settings().get("title_clustering") or {}
        discovered={"method":cluster_cfg.get("method","tfidf_title_similarity_connected_components"),
                    "similarity_threshold":float(cluster_cfg["similarity_threshold"]),"clusters":[],"rows":[]}
    assignment=assign_title_cluster(title,discovered)
    associations=adapter.latest_packaging_associations(None) if adapter else {"run":None,"hero_category":None,"channel":[],"category":[]}
    source_run_id=((associations.get("run") or {}).get("id"))
    if cluster_db is not None and historical:
        persist_title_clusters(cluster_db,discovered,source_run_id=source_run_id)
    cluster_rows=[discovered["rows"][i] for i in (assignment or {}).get("member_indexes",[])]
    prior=eligible_cluster_winners(cluster_rows)
    winner_rows=prior.get("winner_rows") or []
    mechanism=discover_text_mechanisms(winner_rows)
    candidate_audit=transformation_text_candidates(title,mechanism,with_audit=True)
    youtube_examples=[]
    external_text_placement=None
    external_text_placement_evidence=None
    external_structural_layout=None
    external_structural_layout_evidence=None
    external_visible_subjects=[]
    youtube_fallback={"status":"not_needed","reason":"recurrent_local_text_mechanism_available"}
    # YouTube visual composition evidence is independent from the text-copy fallback.
    # When a provider is configured, analyze same-topic references even if local text
    # evidence already produced candidates. External text may replace local copy only
    # when the local lane has no reusable candidate.
    local_candidate_available=bool(candidate_audit)
    if youtube_provider is not None:
        refresh=clear_youtube_reference_thumbnails(project.name)
        refs=collect_references(provider=youtube_provider,topic=title,category="",limit_per_query=12)
        youtube_examples=analyze_youtube_reference_thumbnails(refs,project=project.name,text_analyzer=youtube_text_analyzer)
        external_rows=[]
        diagnostics={
            "fresh_thumbnail_refresh":refresh,
            "reference_count":len(youtube_examples),
            "thumbnail_analyzed":0,
            "thumbnail_failed":0,
            "ocr_available":0,
            "ocr_unavailable":0,
            "ocr_text_found":0,
            "visual_text_found":0,
            "text_placement_found":0,
            "structural_layout_found":0,
            "visible_subject_found":0,
        }
        for ref in youtube_examples:
            status=ref.get("thumbnail_analysis_status")
            if status=="analyzed":
                diagnostics["thumbnail_analyzed"]+=1
            elif status in ("failed","unavailable"):
                diagnostics["thumbnail_failed"]+=1
            ocr=ref.get("external_thumbnail_ocr") or {}
            text=ocr.get("text") if isinstance(ocr,dict) else None
            if isinstance(ocr,dict) and ocr.get("available") is True:
                diagnostics["ocr_available"]+=1
            elif isinstance(ocr,dict) and ocr.get("available") is False:
                diagnostics["ocr_unavailable"]+=1
            if text:
                diagnostics["ocr_text_found"]+=1
            visual_text=str(ref.get("external_thumbnail_visual_text") or "").strip()
            if visual_text:
                diagnostics["visual_text_found"]+=1
            if ref.get("external_thumbnail_text_placement") in ("left","center","right"):
                diagnostics["text_placement_found"]+=1
            if ref.get("external_thumbnail_structural_layout") in ("text_left_subject_right","subject_left_text_right","text_top_subject_bottom","subject_top_text_bottom","centered_subject"):
                diagnostics["structural_layout_found"]+=1
            visible_subject=str(ref.get("external_thumbnail_visible_subject") or "").strip()
            if visible_subject:
                diagnostics["visible_subject_found"]+=1
                external_visible_subjects.append(visible_subject)
            effective_text=str(text or visual_text or "").strip()
            if ref.get("video_title") and effective_text:
                external_rows.append({"performance":{"title":ref["video_title"]},"ocr":{"text":effective_text}})
        placements,layouts,composition_conflicts=_coherent_youtube_composition_votes(youtube_examples)
        diagnostics["composition_conflicts_rejected"]=composition_conflicts
        if placements:
            from collections import Counter
            diagnostics["text_placement_counts"]=dict(Counter(placements))
        if layouts:
            from collections import Counter
            diagnostics["structural_layout_counts"]=dict(Counter(layouts))
        # Layout selection no longer uses recurrence/supermajority thresholds here.
        # Fresh DB winners are validated in evidence order after composition is built;
        # if none match, the highest-view analyzable YouTube reference supplies layout.
        external_mechanism=discover_text_mechanisms(external_rows)
        # External YouTube thumbnails are reference evidence, never positional
        # word-replacement templates. Reuse only an exact recurrent observed overlay when
        # every lexical word is already supported by the immutable current title.
        # If that conservative lane has no candidate, leave external copy unused and let
        # the title-grounded constraint fallback compose fresh copy below. This prevents
        # Frankenstein overlays assembled from unrelated words across reference thumbnails.
        external_candidates=recurrent_observed_text_candidates(title,external_mechanism,with_audit=True)
        if not local_candidate_available and external_candidates:
            candidate_audit=external_candidates
            mechanism=external_mechanism
            youtube_fallback={"status":"used","text_source":"youtube",**diagnostics,"analyzed_text_pairs":len(external_rows)}
        elif local_candidate_available:
            youtube_fallback={"status":"analyzed_for_composition","text_source":"local_cluster",**diagnostics,"analyzed_text_pairs":len(external_rows)}
        else:
            youtube_fallback={"status":"searched_no_recurrent_text_mechanism",**diagnostics,"analyzed_text_pairs":len(external_rows)}
    elif not candidate_audit:
        youtube_fallback={"status":"unavailable","reason":"youtube_provider_not_configured"}
    if not candidate_audit:
        # External reference copy may be unusable even when its mechanism was observed.
        # Compose the fallback from the current immutable title using the best available
        # structural profile. If the local cluster has no ready profile, the external
        # mechanism may supply structure only; its literal words are never copied here.
        fallback_mechanism=mechanism
        if fallback_mechanism.get("status")!="ready" and youtube_provider is not None:
            fallback_mechanism=external_mechanism
        candidate_audit=constraint_text_candidates(title,fallback_mechanism,with_audit=True)
    # Final cross-lane guard: reject mechanically clipped prefixes regardless of which
    # evidence lane produced them. This uses only immutable-title structure; no topic
    # vocabulary or project-specific phrase is hardcoded.
    candidate_audit=filter_incomplete_title_prefix_candidates(title,candidate_audit)
    fresh_text_candidates=[x["text"] for x in candidate_audit]
    # V2 hero categories are retained only as raw evidence metadata; they do not define the new cluster taxonomy.
    context={"immutable_title":title,"requested_category":(assignment or {}).get("cluster_id") or "unclustered",
             "winner_prior":{"winner_examples":winner_rows},"youtube_examples":youtube_examples,"packaging_associations":associations}
    concept=build_concept_direction(context)
    concept["concept"]["thumbnail_text_examples"]=[]
    concept["concept"]["thumbnail_text_candidates"]=fresh_text_candidates
    concept["evidence"]["historical_text_mechanism"]=mechanism
    concept["evidence"]["cluster_prior_status"]={k:v for k,v in prior.items() if k!="winner_rows"}
    concept["evidence"]["thumbnail_text_candidate_ranking"]=candidate_audit
    concept["evidence"]["youtube_fallback"]=youtube_fallback
    concept["evidence"]["youtube_reference_rows"]=youtube_examples
    composition=build_composition_spec(concept)
    layout_winners=adapter.qualifying_thumbnail_layout_winners() if adapter else []
    selected_layout=_select_data_driven_layout(layout_winners,youtube_examples)
    if selected_layout:
        composition["composition"]["layout"]=selected_layout["layout"]
        if selected_layout.get("text_placement"):
            composition["composition"]["text_placement"]=selected_layout["text_placement"]
        if selected_layout.get("subject_placement"):
            composition["composition"]["subject_placement"]=selected_layout["subject_placement"]
        resolved={"layout"}
        if selected_layout.get("text_placement"): resolved.add("text_placement")
        if selected_layout.get("subject_placement"): resolved.add("subject_placement")
        composition["human_review_required_for"]=[
            x for x in composition.get("human_review_required_for",[]) if x not in resolved
        ]
        signature=selected_layout.get("structural_signature") or {}
        composition["composition"]["structural_signature"]={k:v for k,v in signature.items() if v}
        composition["provenance"]["layout_selection"]="data_driven_db_winner_then_youtube"
        composition["provenance"]["layout_selection_evidence"]=selected_layout
        composition["provenance"]["qualifying_db_winner_count"]=len(layout_winners)
    if fresh_text_candidates:
        composition["composition"]["thumbnail_text_candidates"]=fresh_text_candidates
    if external_visible_subjects:
        ranked_visible_subjects=_rank_visible_subjects(external_visible_subjects,title)
        if selected_layout and selected_layout.get("winner_visual_strategy")=="object_led":
            human_terms=("man ","woman ","person ","presenter","portrait","face","finger")
            object_examples=[x for x in ranked_visible_subjects if not any(term in x.casefold() for term in human_terms)]
            if object_examples:
                ranked_visible_subjects=object_examples
            composition["composition"]["visual_strategy"]="object_led_no_presenter"
        elif selected_layout and selected_layout.get("winner_visual_strategy")=="presenter_led":
            composition["composition"]["visual_strategy"]="presenter_led"
        composition["composition"]["visual_subject_examples"]=ranked_visible_subjects[:5]
        composition["provenance"]["visual_subject_examples_source"]="youtube_visible_pixels"
    winner_report=[
        {"rank":i+1,"title":w.get("title"),"ctr":w.get("ctr"),"impressions":w.get("impressions"),
         "layout":w.get("composition_layout"),"layout_family":_layout_family(w.get("composition_layout")),
         "attribution_status":w.get("attribution_status")}
        for i,w in enumerate(layout_winners)
    ]
    return {"project":project.name,"immutable_title":title,"concept":concept,"composition":composition,
            "db_layout_winners":winner_report,"selected_layout":selected_layout,
            "discovered_cluster":assignment,"cluster_count":len(discovered.get("clusters") or [])}

def _load_final_script(project: Path) -> tuple[Path | None, str | None]:
    """Read the final script from the project without modifying V2 project files."""
    candidates=[
        project/"06_final_script.md",
        project/"06_final_script.txt",
        project/"final_script.md",
        project/"final_script.txt",
    ]
    for path in candidates:
        if path.is_file():
            text=path.read_text(encoding="utf-8",errors="replace").strip()
            if text:
                return path,text
    return None,None

def _script_support_contract(api_key: str, *, model: str, immutable_title: str, selected_text: str | None, script_text: str) -> dict[str, Any]:
    """Extract a conservative script-grounding contract for thumbnail semantics."""
    import urllib.request
    instruction="""Audit a YouTube thumbnail promise against the supplied FINAL SCRIPT.
The FINAL SCRIPT is the semantic ceiling. Do not add facts, symptoms, outcomes, mechanisms, counts, timing, product forms, or visual implications that the script does not support.
The immutable title is context, not proof. A title claim is allowed in the thumbnail only when the final script materially delivers it.
For numbered/list promises, verify that the script contains the promised number of clearly identifiable supported items. Do not infer missing items.
Return concise atomic concepts that are safe to communicate in thumbnail text or imagery. Visual concepts must be directly supported by the script; do not invent anatomy, effects, props, dosage forms, packaging, clocks, foods, or symptoms merely because they are visually convenient.
Verdict PASS only when the selected thumbnail headline/promise is materially supported by the final script. Otherwise FAIL and explain the mismatch. Never rewrite the immutable title."""
    schema={
        "type":"object",
        "properties":{
            "verdict":{"type":"string","enum":["PASS","FAIL"]},
            "supported_concepts":{"type":"array","items":{"type":"string"}},
            "supported_visual_concepts":{"type":"array","items":{"type":"string"}},
            "unsupported_or_overstated":{"type":"array","items":{"type":"string"}},
            "count_promise":{"type":["object","null"],"properties":{
                "promised":{"type":["integer","null"]},
                "supported":{"type":["integer","null"]},
                "clearly_identifiable":{"type":"boolean"}
            },"required":["promised","supported","clearly_identifiable"],"additionalProperties":False},
            "reason":{"type":"string"}
        },
        "required":["verdict","supported_concepts","supported_visual_concepts","unsupported_or_overstated","count_promise","reason"],
        "additionalProperties":False
    }
    prompt=instruction+"\n\nIMMUTABLE_TITLE: "+immutable_title+"\nSELECTED_THUMBNAIL_TEXT: "+str(selected_text or "")+"\n\nFINAL_SCRIPT:\n"+script_text
    payload={"model":model,"input":[{"role":"user","content":[{"type":"input_text","text":prompt}]}],
             "text":{"format":{"type":"json_schema","name":"thumbnail_script_support","strict":False,"schema":schema}}}
    req=urllib.request.Request("https://api.openai.com/v1/responses",data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json","User-Agent":"SeniorHealthAI-ThumbnailPipeline/1.0"},method="POST")
    with urllib.request.urlopen(req,timeout=120) as response:
        body=json.loads(response.read().decode("utf-8"))
    output_text=str(body.get("output_text") or "").strip()
    if not output_text:
        for item in body.get("output") or []:
            for part in item.get("content") or []:
                if part.get("type")=="output_text":
                    output_text=str(part.get("text") or "").strip()
                    if output_text: break
            if output_text: break
    result=json.loads(output_text)
    if not isinstance(result,dict):
        raise ValueError("Script support audit must return a JSON object.")
    return result

def _validate_thumbnail_contract(api_key: str, *, model: str, immutable_title: str, selected_text: str | None, script_support: dict[str, Any], winner_metadata: dict[str, Any], adaptation: dict[str, Any]) -> dict[str, Any]:
    """Final semantic gate: generated thumbnail contract may not reinterpret script support."""
    import urllib.request
    instruction="""Validate a GENERATED THUMBNAIL CONTRACT against SCRIPT_SUPPORT_JSON.
SCRIPT_SUPPORT_JSON is the semantic ceiling. Judge the complete contract, including banner, headline, box, callout, primary visual, secondary visual, and attention target.
PASS only when every non-style semantic claim and visual implication is directly supported without strengthening, causal reinterpretation, category substitution, or invented specificity.
Examples of failure patterns: turning 'reasons a supplement may seem not to work' into 'the supplement fails at night'; calling medicines or other products 'supplemental sources' when the support contract does not say that; inventing exact times, dosage forms, symptoms, outcomes, mechanisms, or product relationships.
The immutable selected thumbnail copy must still be supported and must appear verbatim exactly once across the generated text slots, but its physical slot is NOT immutable. Do not fail merely because it moved away from primary_headline to preserve the winner's reading flow, and do not fail merely because optional slots are absent.
CASTING/STYLING CARVE-OUT: A neutral presenter description such as "person", "adult person", "adult", "man", or "woman" is a rendering/casting instruction when WINNER_METADATA authorizes a presenter/person role; it is not by itself a viewer-facing demographic or age claim and must not fail this gate. Flag demographics only when the generated contract invents specific age/audience targeting (for example "60+", "65-year-old", "senior") or ties a demographic attribute to a health promise/outcome that SCRIPT_SUPPORT_JSON does not support.
IMMUTABLE_TITLE is read-only context and is NOT a generated thumbnail-contract slot. Never return immutable_title in unsupported_slots and never fail this gate solely because wording in IMMUTABLE_TITLE is absent from SCRIPT_SUPPORT_JSON. Validate only the generated contract fields listed above; the selected thumbnail headline is the only immutable generated copy audited here.
WINNER_METADATA_JSON is the authority for reusable composition/style/role semantics. A neutral presenter/person anchor, its winner-defined zone, neutral gaze/pointing/attention gesture, and non-semantic arrows/rings used only as attention devices do NOT require independent support from SCRIPT_SUPPORT_JSON when those roles/devices are present in WINNER_METADATA_JSON. Do not fail a slot merely because such winner-authorized structural details are absent from SCRIPT_SUPPORT_JSON. SCRIPT_SUPPORT_JSON remains the semantic ceiling for current-topic claims, medical implications, demographics/age, symptoms, outcomes, mechanisms, and topic-specific objects/details. A presenter role does not authorize inventing doctor/clinician status, age, disease state, treatment effect, or any other topic claim.
Return slot-specific findings. Do not repair or rewrite the contract."""
    schema={"type":"object","properties":{
        "verdict":{"type":"string","enum":["PASS","FAIL"]},
        "unsupported_slots":{"type":"array","items":{"type":"object","properties":{
            "slot":{"type":"string"},"value":{"type":["string","null"]},"reason":{"type":"string"}
        },"required":["slot","value","reason"],"additionalProperties":False}},
        "reason":{"type":"string"}},
        "required":["verdict","unsupported_slots","reason"],"additionalProperties":False}
    prompt=instruction+"\n\nIMMUTABLE_TITLE: "+immutable_title+"\nSELECTED_THUMBNAIL_TEXT: "+str(selected_text or "")+"\nSCRIPT_SUPPORT_JSON:\n"+json.dumps(script_support,ensure_ascii=False)+"\nWINNER_METADATA_JSON:\n"+json.dumps(winner_metadata,ensure_ascii=False)+"\nGENERATED_THUMBNAIL_CONTRACT:\n"+json.dumps({k:v for k,v in adaptation.items() if k!="adaptation_rationale"},ensure_ascii=False)
    payload={"model":model,"input":[{"role":"user","content":[{"type":"input_text","text":prompt}]}],
             "text":{"format":{"type":"json_schema","name":"thumbnail_final_semantic_gate","strict":False,"schema":schema}}}
    req=urllib.request.Request("https://api.openai.com/v1/responses",data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json","User-Agent":"SeniorHealthAI-ThumbnailPipeline/1.0"},method="POST")
    with urllib.request.urlopen(req,timeout=120) as response:
        body=json.loads(response.read().decode("utf-8"))
    output_text=str(body.get("output_text") or "").strip()
    if not output_text:
        for item in body.get("output") or []:
            for part in item.get("content") or []:
                if part.get("type")=="output_text":
                    output_text=str(part.get("text") or "").strip()
                    if output_text: break
            if output_text: break
    result=json.loads(output_text)
    if not isinstance(result,dict):
        raise ValueError("Final thumbnail semantic gate must return a JSON object.")
    return result

def _validate_thumbnail_utility(api_key: str, *, model: str, immutable_title: str, selected_text: str | None, script_support: dict[str, Any], winner_metadata: dict[str, Any], adaptation: dict[str, Any]) -> dict[str, Any]:
    """Coverage/utility gate: require useful script-supported use of high-value winner roles."""
    import urllib.request
    instruction="""Evaluate a script-grounded GENERATED THUMBNAIL CONTRACT for information coverage and use of the proven WINNER_METADATA architecture.
This is NOT a safety gate. SCRIPT_SUPPORT_JSON already defines what is allowed. Judge whether the contract uses distinct, high-value supported concepts efficiently while preserving the winner's useful composition roles.
Rules:
- Winner slots are capacity, not a quota. Never demand filler, duplicate copy, or invented imagery.
- Empty is valid. Script-supported visuals are a candidate pool, not a placement checklist. Never require secondary_detail/attention_target merely because another supported concept exists; use an optional role only when it materially improves the winner-sized hook without adding a separate competing informational object. Default to empty on ties.
- Banner, headline, boxed keyword, and callout should carry different marginal information. Penalize repetition and weak generic copy. Optional text slots may be null; never require a replacement merely to fill capacity.
- REQUIRED-VS-OPTIONAL IS DETERMINISTIC ONLY. Unless a text band has an explicit machine-readable required=true field in the structural contract, treat that band as OPTIONAL. Historical visible copy, semantic_structure prose, reusable_composition_contract prose, labels such as CTA/imperative_cta, style_role names, or the fact that the old winner used an imperative MUST NOT create a required current-topic band. Never fail because bottom_callout/CTA is null when no deterministic required=true field exists. A script-supported CTA such as CHECK LABELS may be used when it adds distinct marginal value, but it is never mandatory merely because the historical winner had a CTA.
- Preserve the WINNER_METADATA text-flow relationship, not merely the number and positions of text boxes. If semantic_structure/reusable_composition_contract shows that historical bands form one progressive or continuous hook, judge the adapted bands as one reading sequence: each visible band must naturally continue/complete the same current-topic message. Unrelated standalone facts or a detached CTA that make the sequence fragmented are actionable defects. Prefer collapsing/nulling optional bands over filling every historical band. If the winner instead visibly uses independent messages, do not falsely require a continuous sentence.
- SELECTED_THUMBNAIL_TEXT is immutable copy, not an immutable band assignment. Require it verbatim exactly once across the visible text slots, but allow it to move to whichever band makes the winner's reading sequence coherent. Never demand that it remain primary_headline solely because of the field name.
- Historical winner topic semantics are NOT immutable architecture. Preserve the reusable relationship and hierarchy (for example presenter -> gesture/attention device -> target), but the historical target itself (body part, food, symptom, product, etc.) MUST be replaced by an appropriate current-topic target supported by SCRIPT_SUPPORT_JSON. Do not fail merely because the presenter now points to a different current-topic object or because arrows/rings moved from the historical body/object target to that new supported target.
- Winner role descriptions such as 'body-focused', historical anatomy, historical object identity, or historical semantic CTA wording are evidence of the old topic, not permanent target semantics. Geometry/role hierarchy may be retained while semantic occupants change.
- Text-role formatting (single word, CTA, character count, imperative wording) is a reusable constraint only when WINNER_METADATA explicitly marks it as immutable/reusable in reusable_composition_contract; do not infer a hard requirement merely from the historical visible copy.
- Prefer the strongest intersection of immutable-title tension and script support; do not drift to a secondary angle merely because it is technically supported.
- Primary and secondary visuals should communicate different supported tokens. Attention devices must point to one unique informative current-topic referent, and presenter gesture/attention mapping should align to that same referent.
- Do not invent or strengthen claims in order to improve utility.
PASS only when the contract is both economical and makes good use of available script-supported information and the reusable winner architecture.
STRICT VERDICT RULE: findings are actionable contract defects. If any finding requires changing generated text, a visual, an attention target, or geometry/hierarchy mapping, verdict MUST be FAIL. PASS requires findings=[] and no contract change needed. Do not report praise, observations, or internal rationale-only inconsistencies as findings.
Evaluate only generation-visible contract fields: top_banner, primary_headline, boxed_keyword, bottom_callout, primary_visual, secondary_detail, attention_target. Ignore adaptation_rationale completely because it is internal diagnostic text and is not exported to the generation prompt.
Return actionable findings only; do not rewrite the contract."""
    schema={"type":"object","properties":{
        "verdict":{"type":"string","enum":["PASS","FAIL"]},
        "findings":{"type":"array","items":{"type":"object","properties":{
            "area":{"type":"string"},"reason":{"type":"string"}
        },"required":["area","reason"],"additionalProperties":False}},
        "reason":{"type":"string"}},
        "required":["verdict","findings","reason"],"additionalProperties":False}
    prompt=instruction+"\n\nIMMUTABLE_TITLE: "+immutable_title+"\nSELECTED_THUMBNAIL_TEXT: "+str(selected_text or "")+"\nSCRIPT_SUPPORT_JSON:\n"+json.dumps(script_support,ensure_ascii=False)+"\nWINNER_METADATA_JSON:\n"+json.dumps(winner_metadata,ensure_ascii=False)+"\nGENERATED_THUMBNAIL_CONTRACT:\n"+json.dumps(adaptation,ensure_ascii=False)
    payload={"model":model,"input":[{"role":"user","content":[{"type":"input_text","text":prompt}]}],
             "text":{"format":{"type":"json_schema","name":"thumbnail_coverage_utility_gate","strict":False,"schema":schema}}}
    req=urllib.request.Request("https://api.openai.com/v1/responses",data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json","User-Agent":"SeniorHealthAI-ThumbnailPipeline/1.0"},method="POST")
    with urllib.request.urlopen(req,timeout=120) as response:
        body=json.loads(response.read().decode("utf-8"))
    output_text=str(body.get("output_text") or "").strip()
    if not output_text:
        for item in body.get("output") or []:
            for part in item.get("content") or []:
                if part.get("type")=="output_text":
                    output_text=str(part.get("text") or "").strip()
                    if output_text: break
            if output_text: break
    result=json.loads(output_text)
    if not isinstance(result,dict):
        raise ValueError("Thumbnail coverage/utility gate must return a JSON object.")
    return result

def main() -> int:
    parser=argparse.ArgumentParser(description="Thumbnail Pipeline prompt-only project CLI")
    parser.add_argument("--project",required=True,help="Exact folder name under Projects/")
    parser.add_argument("--projects-root",default="Projects")
    parser.add_argument("--analytics-db",default="Analytics/senior_health_analytics.db",help="Read-only historical analytics DB")
    parser.add_argument("--cluster-db",default="Thumbnail_Pipeline/db/thumbnail_intelligence.db",help="Pipeline-owned derived intelligence DB")
    parser.add_argument("--layout")
    parser.add_argument("--subject-placement")
    parser.add_argument("--text-placement")
    parser.add_argument("--safe-zone")
    parser.add_argument("--thumbnail-text")
    parser.add_argument("--youtube-client-json",default=os.environ.get("V2_YOUTUBE_CLIENT_JSON"),help="Existing V2 OAuth client JSON; read only")
    parser.add_argument("--youtube-token-json",default=os.environ.get("V2_YOUTUBE_TOKEN_JSON"),help="Existing V2 OAuth token JSON; never modified")
    parser.add_argument("--vision-api-key",default=os.environ.get("OPENAI_API_KEY"),help="Optional OpenAI API key for thumbnail text vision fallback")
    parser.add_argument("--vision-model",default=os.environ.get("THUMBNAIL_VISION_MODEL","gpt-5-mini"),help="Vision-capable model used only when local OCR has no text")
    args=parser.parse_args()
    project=resolve_project(args.project,args.projects_root)
    youtube_provider=None
    client_path=Path(args.youtube_client_json) if args.youtube_client_json else None
    token_path=Path(args.youtube_token_json) if args.youtube_token_json else None
    if not (client_path and token_path):
        discovered_client,discovered_token=discover_v2_youtube_oauth_files_read_only(Path("."))
        client_path=client_path or discovered_client
        token_path=token_path or discovered_token
    if client_path and token_path:
        token=access_token_from_v2_files_read_only(client_path,token_path)
        youtube_provider=V2YouTubeReferenceProvider(token)
    youtube_text_analyzer=openai_thumbnail_text_analyzer(args.vision_api_key,model=args.vision_model) if args.vision_api_key else None
    state=build_project_prompt_state(project,Path(args.analytics_db),cluster_db=Path(args.cluster_db),youtube_provider=youtube_provider,youtube_text_analyzer=youtube_text_analyzer)
    spec=state["composition"]
    print("DB LAYOUT WINNERS")
    print("=================")
    winners=state.get("db_layout_winners") or []
    if not winners:
        print("No qualifying DB winners (CTR >= 6%, impressions >= 5,000).")
    else:
        for row in winners:
            print(f'#{row["rank"]} | {row["title"]}')
            print(f'  CTR: {float(row["ctr"]):.4f}% | Impressions: {int(row["impressions"]):,} | Attribution: {row["attribution_status"]}')
            print(f'  Layout family: {row["layout_family"] or "unclassified"}')
            print(f'  Layout: {row["layout"]}')
    print("\nLAYOUT SELECTION")
    print("================")
    selected=state.get("selected_layout")
    if selected:
        print(json.dumps(selected,indent=2,ensure_ascii=False))
    else:
        print("No data-backed layout could be selected.")
    refresh=((state["concept"].get("evidence") or {}).get("youtube_fallback") or {}).get("fresh_thumbnail_refresh")
    if refresh:
        print("\nYOUTUBE THUMBNAIL REFRESH")
        print("=========================")
        print(f'Old cached thumbnails removed: {refresh.get("removed_thumbnail_files",0)}')
        print(f'Fresh reference output: {refresh.get("output_dir")}')
    corrections={k:v for k,v in {
        "layout":args.layout,
        "subject_placement":args.subject_placement,
        "text_placement":args.text_placement,
        "safe_zone":args.safe_zone,
    }.items() if v}
    if corrections:
        spec=apply_composition_review(spec,corrections=corrections,notes="Explicit CLI human review")
    gate=evaluate_generation_gate(spec)
    if not gate["approved"]:
        print(json.dumps({
            "status":"needs_human_review",
            "project":state["project"],
            "immutable_title":state["immutable_title"],
            "unresolved_fields":gate["unresolved_fields"],
            "thumbnail_text_candidates":(spec.get("composition") or {}).get("thumbnail_text_candidates") or [],
            "discovered_cluster":state.get("discovered_cluster"),
            "cluster_count":state.get("cluster_count"),
            "packaging_association_run":(state["concept"].get("evidence") or {}).get("packaging_association_run"),
            "youtube_fallback":(state["concept"].get("evidence") or {}).get("youtube_fallback"),
            "instruction":"Resolve only fields not supported by DB evidence. No image generation, upload, or V2 write was performed.",
        },indent=2,ensure_ascii=False))
        return 2
    selected_text=args.thumbnail_text
    if selected_text is None:
        candidates=(spec.get("composition") or {}).get("thumbnail_text_candidates") or []
        selected_text=candidates[0] if candidates else None
    winner_metadata_analyzer=openai_winner_metadata_analyzer(args.vision_api_key,model=args.vision_model) if args.vision_api_key else None
    winner_metadata=build_fresh_winner_metadata(project=state["project"],selected_layout=state.get("selected_layout") or {},youtube_rows=((state["concept"].get("evidence") or {}).get("youtube_reference_rows") or []),metadata_analyzer=winner_metadata_analyzer)
    fresh_metadata=winner_metadata.get("metadata") if winner_metadata.get("status")=="ready" else None
    # Script-grounding gate: title is context, but the final script is the semantic ceiling.
    script_path,script_text=_load_final_script(project)
    script_support=None
    if script_text and args.vision_api_key:
        script_support=_script_support_contract(args.vision_api_key,model=args.vision_model,immutable_title=state["immutable_title"],selected_text=selected_text,script_text=script_text)
        support_dir=Path("Thumbnail_Pipeline")/"outputs"/str(state["project"])/"json"
        support_dir.mkdir(parents=True,exist_ok=True)
        (support_dir/"script_support.json").write_text(json.dumps(script_support,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        print("\nSCRIPT GROUNDING")
        print("================")
        print(f"Final script: {script_path}")
        print(json.dumps(script_support,indent=2,ensure_ascii=False))
        if script_support.get("verdict")!="PASS":
            print("\nTHUMBNAIL CLAIM GATE: FAIL")
            print("Final thumbnail prompt was not exported because the selected thumbnail promise is not materially supported by the final script.")
            return 3
    elif not script_text:
        print("\nSCRIPT GROUNDING")
        print("================")
        print("THUMBNAIL CLAIM GATE: FAIL")
        print("No final script found in the project. Expected 06_final_script.md/.txt (or final_script.md/.txt).")
        return 3
    elif not args.vision_api_key:
        print("\nSCRIPT GROUNDING")
        print("================")
        print("THUMBNAIL CLAIM GATE: FAIL")
        print("Final script exists, but no vision/API key is available to perform the script-support audit.")
        return 3

    topic_adaptation=None
    final_semantic_gate=None
    if fresh_metadata and args.vision_api_key:
        topic_adapter=openai_current_topic_adapter(args.vision_api_key,model=args.vision_model)
        support_dir=Path("Thumbnail_Pipeline")/"outputs"/str(state["project"])/"json"
        max_contract_attempts=3
        revision_feedback=None
        prior_contract=None
        for attempt in range(1,max_contract_attempts+1):
            topic_adaptation=topic_adapter(
                metadata=fresh_metadata,
                immutable_title=state["immutable_title"],
                selected_text=selected_text,
                script_support=script_support,
                revision_feedback=revision_feedback,
                prior_contract=prior_contract,
            )
            print(f"\nTHUMBNAIL CONTRACT ATTEMPT {attempt}/{max_contract_attempts}")
            print("================================")

            final_semantic_gate=_validate_thumbnail_contract(
                args.vision_api_key,model=args.vision_model,
                immutable_title=state["immutable_title"],selected_text=selected_text,
                script_support=script_support,winner_metadata=fresh_metadata,adaptation=topic_adaptation,
            )
            (support_dir/"final_semantic_gate.json").write_text(json.dumps(final_semantic_gate,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
            print("\nFINAL THUMBNAIL SEMANTIC GATE")
            print("=============================")
            print(json.dumps(final_semantic_gate,indent=2,ensure_ascii=False))
            if final_semantic_gate.get("verdict")!="PASS":
                prior_contract=topic_adaptation
                revision_feedback={"gate":"semantic","attempt":attempt,"result":final_semantic_gate}
                if attempt<max_contract_attempts:
                    print("\nFINAL THUMBNAIL SEMANTIC GATE: FAIL — revising contract")
                    continue
                print("\nFINAL THUMBNAIL SEMANTIC GATE: FAIL")
                print("Maximum contract attempts reached; final prompt was not exported.")
                return 4

            utility_gate=_validate_thumbnail_utility(
                args.vision_api_key,model=args.vision_model,
                immutable_title=state["immutable_title"],selected_text=selected_text,
                script_support=script_support,winner_metadata=fresh_metadata,
                adaptation=topic_adaptation,
            )
            (support_dir/"coverage_utility_gate.json").write_text(json.dumps(utility_gate,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
            print("\nTHUMBNAIL COVERAGE / UTILITY GATE")
            print("=================================")
            print(json.dumps(utility_gate,indent=2,ensure_ascii=False))
            if utility_gate.get("verdict")=="PASS":
                break
            prior_contract=topic_adaptation
            revision_feedback={"gate":"coverage_utility","attempt":attempt,"result":utility_gate}
            if attempt<max_contract_attempts:
                print("\nTHUMBNAIL COVERAGE / UTILITY GATE: FAIL — revising contract")
                continue
            print("\nTHUMBNAIL COVERAGE / UTILITY GATE: FAIL")
            print("Maximum contract attempts reached; final prompt was not exported.")
            return 5

    if not isinstance(fresh_metadata,dict) or not isinstance(fresh_metadata.get("structural_contract"),dict):
        print("\nPRE-GENERATION CONTRACT QA: FAIL")
        print("Fresh winner structural_contract is required; prompt was not exported.")
        return 6
    render_structure=build_render_structure(fresh_metadata,topic_adaptation or {},selected_text)
    contract_qa=evaluate_contract_qa(render_structure)
    (support_dir/"contract_qa.json").write_text(json.dumps(contract_qa,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("\nPRE-GENERATION CONTRACT QA")
    print("==========================")
    print(json.dumps({"verdict":contract_qa["verdict"],"findings":contract_qa["findings"]},indent=2,ensure_ascii=False))
    if contract_qa["verdict"]!="PASS":
        print("PRE-GENERATION CONTRACT QA: FAIL — final prompt was not exported.")
        return 6

    result=export_final_thumbnail_prompt(spec,gate,selected_text=selected_text,winner_metadata=fresh_metadata,topic_adaptation=topic_adaptation,render_structure=render_structure)
    prompt_output_dir=Path("Thumbnail_Pipeline")/"outputs"/str(state["project"])
    prompt_output_dir.mkdir(parents=True,exist_ok=True)
    prompt_path=prompt_output_dir/"final_thumbnail_prompt.txt"
    selected_source=state.get("selected_layout") or {}
    source_lines=["WINNER SOURCE","============="]
    if selected_source.get("winner_title"):
        source_lines += [f"Winner Title: {selected_source.get('winner_title')}",f"CTR: {float(selected_source.get('winner_ctr') or 0):.4f}%",f"Impressions: {int(selected_source.get('winner_impressions') or 0):,}"]
        if selected_source.get("winner_video_id"): source_lines.append(f"Winner Video ID: {selected_source.get('winner_video_id')}")
        if selected_source.get("winner_video_url"): source_lines.append(f"Winner Video URL: {selected_source.get('winner_video_url')}")
        source_lines.append(f"Winner Visual Strategy: {selected_source.get('winner_visual_strategy') or 'unknown'}")
        source_lines.append(f"Winner Layout: {selected_source.get('historical_layout_evidence') or selected_source.get('layout')}")
        source_lines.append("Winner Structural Signature: "+json.dumps(selected_source.get("structural_signature") or {},ensure_ascii=False))
    else:
        source_lines.append("No DB winner selected; layout used YouTube fallback evidence.")
    if winner_metadata.get("thumbnail_path"): source_lines.append(f"Fresh Winner Thumbnail: {winner_metadata.get('thumbnail_path')}")
    if winner_metadata.get("metadata_path"): source_lines.append(f"Fresh Winner Metadata JSON: {winner_metadata.get('metadata_path')}")
    source_lines += ["","FINAL THUMBNAIL PROMPT","======================"]
    prompt_path.write_text("\n".join(source_lines)+"\n"+result["final_prompt"]+"\n",encoding="utf-8")
    print("FINAL THUMBNAIL PROMPT")
    print("======================")
    print(result["final_prompt"])
    print("\nWINNER METADATA")
    print("===============")
    print(f"Status: {winner_metadata.get('status')}")
    if winner_metadata.get("thumbnail_path"): print(f"Fresh thumbnail: {winner_metadata.get('thumbnail_path')}")
    if winner_metadata.get("metadata_path"): print(f"Fresh metadata JSON: {winner_metadata.get('metadata_path')}")
    print(f"\nPrompt saved: {prompt_path}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())

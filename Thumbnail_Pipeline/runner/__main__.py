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
from Thumbnail_Pipeline.intelligence.text_mechanisms import discover_text_mechanisms, transformation_text_candidates, constraint_text_candidates, recurrent_observed_text_candidates
from Thumbnail_Pipeline.adapters.youtube_reference import collect_references
from Thumbnail_Pipeline.adapters.youtube_thumbnail_analysis import analyze_youtube_reference_thumbnails, openai_thumbnail_text_analyzer
from Thumbnail_Pipeline.adapters.v2_youtube_api import V2YouTubeReferenceProvider, access_token_from_v2_files_read_only

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
    seen=set(); ranked=[]
    for i,raw in enumerate(subjects):
        value=" ".join(str(raw or "").split()).strip()
        key=value.casefold()
        if not value or key in seen: continue
        seen.add(key)
        tokens=set(re.findall(r"[a-z0-9]+",key))
        overlap=len(tokens & title_tokens)
        specificity=sum(1 for x in tokens if len(x)>=5)
        ranked.append((overlap,specificity,len(tokens),-i,value))
    ranked.sort(reverse=True)
    return [x[-1] for x in ranked]

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
        refs=collect_references(provider=youtube_provider,topic=title,category="",limit_per_query=12)
        youtube_examples=analyze_youtube_reference_thumbnails(refs,project=project.name,text_analyzer=youtube_text_analyzer)
        external_rows=[]
        diagnostics={
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
        placements=[str(r.get("external_thumbnail_text_placement")) for r in youtube_examples
                    if r.get("external_thumbnail_text_placement") in ("left","center","right")]
        if placements:
            from collections import Counter
            placement_counts=Counter(placements)
            top,count=placement_counts.most_common(1)[0]
            total=len(placements)
            # Resolve only on a recurrent supermajority; otherwise human review remains.
            if count >= 3 and (count/total) >= 0.60:
                external_text_placement=top
                external_text_placement_evidence={"source":"youtube_visual_recurrence","observations":total,
                                                  "supporting":count,"share":round(count/total,4),
                                                  "counts":dict(placement_counts)}
        layouts=[str(r.get("external_thumbnail_structural_layout")) for r in youtube_examples
                 if r.get("external_thumbnail_structural_layout") in ("text_left_subject_right","subject_left_text_right","text_top_subject_bottom","subject_top_text_bottom","centered_subject")]
        if layouts:
            from collections import Counter
            layout_counts=Counter(layouts)
            top_layout,layout_count=layout_counts.most_common(1)[0]
            layout_total=len(layouts)
            if layout_count >= 3 and (layout_count/layout_total) >= 0.60:
                external_structural_layout=top_layout
                external_structural_layout_evidence={"source":"youtube_visual_recurrence","observations":layout_total,
                                                     "supporting":layout_count,"share":round(layout_count/layout_total,4),
                                                     "counts":dict(layout_counts)}
        external_mechanism=discover_text_mechanisms(external_rows)
        # External YouTube evidence is not a positional word-replacement template.
        # First preserve genuinely recurrent observed copy when its words are supported by
        # the immutable title. Only if none survives do we try the legacy transformation.
        external_candidates=recurrent_observed_text_candidates(title,external_mechanism,with_audit=True)
        if not external_candidates:
            external_candidates=transformation_text_candidates(title,external_mechanism,with_audit=True)
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
        candidate_audit=constraint_text_candidates(title,mechanism,with_audit=True)
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
    composition=build_composition_spec(concept)
    # YouTube visual structural layout is secondary evidence and resolves only on
    # recurrent/supermajority support. It never overrides DB-derived layout.
    if composition["composition"].get("layout") is None and external_structural_layout:
        composition["composition"]["layout"]=external_structural_layout
        composition["provenance"]["layout_derived_from_youtube_visual_recurrence"]=True
        composition["provenance"]["youtube_structural_layout_evidence"]=external_structural_layout_evidence
        composition["human_review_required_for"]=[x for x in composition["human_review_required_for"] if x!="layout"]
    # YouTube visual placement is secondary evidence and can resolve placement only when
    # recurrent/supermajority support exists. It never overrides DB-derived placement.
    if composition["composition"].get("text_placement") is None and external_text_placement:
        composition["composition"]["text_placement"]=external_text_placement
        composition["provenance"]["text_placement_derived_from_youtube_visual_recurrence"]=True
        composition["provenance"]["youtube_text_placement_evidence"]=external_text_placement_evidence
        composition["human_review_required_for"]=[x for x in composition["human_review_required_for"] if x!="text_placement"]
    if fresh_text_candidates:
        composition["composition"]["thumbnail_text_candidates"]=fresh_text_candidates
    if external_visible_subjects:
        ranked_visible_subjects=_rank_visible_subjects(external_visible_subjects,title)
        composition["composition"]["visual_subject_examples"]=ranked_visible_subjects[:5]
        composition["provenance"]["visual_subject_examples_source"]="youtube_visible_pixels"
    return {"project":project.name,"immutable_title":title,"concept":concept,"composition":composition,
            "discovered_cluster":assignment,"cluster_count":len(discovered.get("clusters") or [])}

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
    if args.youtube_client_json and args.youtube_token_json:
        token=access_token_from_v2_files_read_only(Path(args.youtube_client_json),Path(args.youtube_token_json))
        youtube_provider=V2YouTubeReferenceProvider(token)
    youtube_text_analyzer=openai_thumbnail_text_analyzer(args.vision_api_key,model=args.vision_model) if args.vision_api_key else None
    state=build_project_prompt_state(project,Path(args.analytics_db),cluster_db=Path(args.cluster_db),youtube_provider=youtube_provider,youtube_text_analyzer=youtube_text_analyzer)
    spec=state["composition"]
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
    result=export_final_thumbnail_prompt(spec,gate,selected_text=selected_text)
    print("FINAL THUMBNAIL PROMPT")
    print("======================")
    print(result["final_prompt"])
    return 0

if __name__=="__main__":
    raise SystemExit(main())

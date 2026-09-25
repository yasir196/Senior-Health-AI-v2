from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any

from Thumbnail_Pipeline.concept_engine import build_concept_direction
from Thumbnail_Pipeline.composition import build_composition_spec
from Thumbnail_Pipeline.qa import apply_composition_review, evaluate_generation_gate
from Thumbnail_Pipeline.prompt_export import export_final_thumbnail_prompt
from Thumbnail_Pipeline.adapters.v2_analytics_db import V2AnalyticsReadOnlyAdapter

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

def build_project_prompt_state(project: Path, analytics_db: Path | None = None) -> dict[str, Any]:
    meta=_read_project_json(project)
    title=_title(meta)
    category=meta.get("category") or meta.get("topic_category") or "uncategorized"
    associations = V2AnalyticsReadOnlyAdapter(analytics_db).latest_packaging_associations(str(category)) if analytics_db else {"run":None,"hero_category":str(category),"channel":[],"category":[]}
    context={"immutable_title":title,"requested_category":str(category),"winner_prior":{"winner_examples":[]},"youtube_examples":[],"packaging_associations":associations}
    concept=build_concept_direction(context)
    composition=build_composition_spec(concept)
    return {
        "project":project.name,
        "immutable_title":title,
        "concept":concept,
        "composition":composition
    }

def main() -> int:
    parser=argparse.ArgumentParser(description="Thumbnail Pipeline prompt-only project CLI")
    parser.add_argument("--project",required=True,help="Exact folder name under Projects/")
    parser.add_argument("--projects-root",default="Projects")
    parser.add_argument("--analytics-db",default="Analytics/senior_health_analytics.db",help="Read-only historical analytics DB")
    parser.add_argument("--layout")
    parser.add_argument("--subject-placement")
    parser.add_argument("--text-placement")
    parser.add_argument("--safe-zone")
    parser.add_argument("--thumbnail-text")
    args=parser.parse_args()
    project=resolve_project(args.project,args.projects_root)
    state=build_project_prompt_state(project,Path(args.analytics_db))
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
            "packaging_association_run":(state["concept"].get("evidence") or {}).get("packaging_association_run"),
            "instruction":"Resolve only fields not supported by DB evidence. No image generation, upload, or V2 write was performed.",
        },indent=2,ensure_ascii=False))
        return 2
    result=export_final_thumbnail_prompt(spec,gate,selected_text=args.thumbnail_text)
    print("FINAL THUMBNAIL PROMPT")
    print("======================")
    print(result["final_prompt"])
    return 0

if __name__=="__main__":
    raise SystemExit(main())

from __future__ import annotations
from pathlib import Path
from typing import Any
from Thumbnail_Pipeline.adapters.v2_analytics_db import V2AnalyticsReadOnlyAdapter
from Thumbnail_Pipeline.intelligence.runner import run_intelligence
from Thumbnail_Pipeline.intelligence.new_project_context import build_new_project_context_from_v2_youtube

def run_from_v2(db_path: Path, output_dir: str="intelligence")->dict[str,Any]:
    adapter=V2AnalyticsReadOnlyAdapter(Path(db_path))
    rows=adapter.to_intelligence_rows()
    result=run_intelligence(rows,output_dir=output_dir)
    result["source"]="v2_analytics_read_only"
    result["source_rows"]=len(rows)
    result["db_path"]=str(Path(db_path))
    return result


def build_new_project_from_v2(*,db_path:Path,access_token:str,title:str,topic:str,category:str,output_dir:str="intelligence")->dict[str,Any]:
    """End-to-end read-only evidence handoff: V2 analytics -> winners -> V2 OAuth YouTube refs -> new-project context."""
    analysis=run_from_v2(db_path,output_dir=output_dir)
    return build_new_project_context_from_v2_youtube(title=title,topic=topic,category=category,winner_rows=analysis.get("winner_records") or [],access_token=access_token)

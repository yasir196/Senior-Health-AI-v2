from __future__ import annotations
from pathlib import Path
from typing import Any
from Thumbnail_Pipeline.adapters.v2_analytics_db import V2AnalyticsReadOnlyAdapter
from Thumbnail_Pipeline.intelligence.runner import run_intelligence

def run_from_v2(db_path: Path, output_dir: str="intelligence")->dict[str,Any]:
    adapter=V2AnalyticsReadOnlyAdapter(Path(db_path))
    rows=adapter.to_intelligence_rows()
    result=run_intelligence(rows,output_dir=output_dir)
    result["source"]="v2_analytics_read_only"
    result["source_rows"]=len(rows)
    result["db_path"]=str(Path(db_path))
    return result

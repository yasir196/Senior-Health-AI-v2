from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from Thumbnail_Pipeline.intelligence.settings import CONFIG_PATH, load_settings
from Thumbnail_Pipeline.io_policy import safe_output

EDITABLE_SETTINGS=("eligibility.min_impressions","reliability.full_reliability_impressions")

def get_dashboard_settings()->dict[str,Any]:
    cfg=load_settings()
    return {
        "min_impressions":int(cfg["eligibility"]["min_impressions"]),
        "full_reliability_impressions":int(cfg["reliability"]["full_reliability_impressions"]),
        "source":"Thumbnail_Pipeline/config/intelligence.json",
        "editable_in_dashboard":True,
    }

def save_dashboard_settings(*,min_impressions:int,full_reliability_impressions:int,actor:str="dashboard")->dict[str,Any]:
    minimum=int(min_impressions); full=int(full_reliability_impressions)
    if minimum<1: raise ValueError("Minimum impressions must be at least 1.")
    if full<minimum: raise ValueError("Full reliability impressions must be >= minimum impressions.")
    cfg=load_settings()
    before=get_dashboard_settings()
    cfg.setdefault("eligibility",{})["min_impressions"]=minimum
    cfg["eligibility"]["threshold_locked"]=True
    cfg.setdefault("reliability",{})["impression_floor"]=minimum
    cfg["reliability"]["full_reliability_impressions"]=full
    cfg["reliability"]["locked"]=True

    tmp=CONFIG_PATH.with_suffix(CONFIG_PATH.suffix+".tmp")
    tmp.write_text(json.dumps(cfg,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    tmp.replace(CONFIG_PATH)

    after=get_dashboard_settings()
    audit=safe_output("settings/settings_audit.jsonl")
    audit.parent.mkdir(parents=True,exist_ok=True)
    event={"saved_at":datetime.now(timezone.utc).isoformat(),"actor":actor,"before":before,"after":after}
    with audit.open("a",encoding="utf-8") as fh: fh.write(json.dumps(event,ensure_ascii=False)+"\n")
    return after

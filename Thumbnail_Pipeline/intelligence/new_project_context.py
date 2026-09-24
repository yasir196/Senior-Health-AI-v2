from __future__ import annotations
from typing import Any
from .new_project_prior import build_new_project_prior
from .youtube_outlier_contract import combine_new_project_evidence
from Thumbnail_Pipeline.adapters.youtube_reference import collect_references,YouTubeReferenceProvider

def build_new_project_context(*,title:str,topic:str,category:str,winner_rows:list[dict[str,Any]],youtube_provider:YouTubeReferenceProvider|None=None)->dict[str,Any]:
    winner_prior=build_new_project_prior(category=category,winner_rows=winner_rows)
    refs=[] if youtube_provider is None else collect_references(provider=youtube_provider,topic=topic,category=category)
    combined=combine_new_project_evidence(winner_prior=winner_prior,youtube_examples=refs)
    return {
        "immutable_title":title,
        "topic":topic,
        "requested_category":category,
        **combined,
        "youtube_discovery_status":"provider_not_connected" if youtube_provider is None else "complete",
        "youtube_reference_count":len(refs),
    }

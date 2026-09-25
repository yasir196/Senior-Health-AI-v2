from __future__ import annotations
from typing import Any
from .new_project_prior import build_new_project_prior
from .youtube_outlier_contract import combine_new_project_evidence
from Thumbnail_Pipeline.adapters.youtube_reference import collect_references,YouTubeReferenceProvider
from Thumbnail_Pipeline.adapters.v2_youtube_api import V2YouTubeReferenceProvider,access_token_from_v2_files_read_only
from Thumbnail_Pipeline.adapters.youtube_thumbnail_analysis import analyze_youtube_reference_thumbnails

def build_new_project_context(*,title:str,topic:str,category:str,winner_rows:list[dict[str,Any]],youtube_provider:YouTubeReferenceProvider|None=None)->dict[str,Any]:
    winner_prior=build_new_project_prior(category=category,winner_rows=winner_rows)
    refs=[] if youtube_provider is None else collect_references(provider=youtube_provider,topic=topic,category=category)
    if refs: refs=analyze_youtube_reference_thumbnails(refs)
    combined=combine_new_project_evidence(winner_prior=winner_prior,youtube_examples=refs)
    return {
        "immutable_title":title,
        "topic":topic,
        "requested_category":category,
        **combined,
        "youtube_discovery_status":"provider_not_connected" if youtube_provider is None else "complete",
        "youtube_reference_count":len(refs),
    }


def build_new_project_context_from_v2_youtube(*,title:str,topic:str,category:str,winner_rows:list[dict[str,Any]],access_token:str)->dict[str,Any]:
    """Connected runtime path: reuse V2 OAuth token for external YouTube references."""
    provider=V2YouTubeReferenceProvider(access_token)
    return build_new_project_context(title=title,topic=topic,category=category,winner_rows=winner_rows,youtube_provider=provider)


def build_new_project_context_from_v2_oauth_files(*,title:str,topic:str,category:str,winner_rows:list[dict[str,Any]],client_json_path,token_path)->dict[str,Any]:
    token=access_token_from_v2_files_read_only(client_json_path,token_path)
    return build_new_project_context_from_v2_youtube(title=title,topic=topic,category=category,winner_rows=winner_rows,access_token=token)


def build_new_project_concept(*, title: str, topic: str, category: str, winner_rows: list[dict[str, Any]], youtube_provider: YouTubeReferenceProvider | None = None) -> dict[str, Any]:
    """Phase 2 orchestration: evidence context -> traceable concept direction."""
    from Thumbnail_Pipeline.concept_engine import build_concept_direction
    context = build_new_project_context(
        title=title,
        topic=topic,
        category=category,
        winner_rows=winner_rows,
        youtube_provider=youtube_provider,
    )
    return {"context": context, "concept_direction": build_concept_direction(context)}

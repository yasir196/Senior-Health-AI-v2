from __future__ import annotations
from typing import Any, Protocol
from Thumbnail_Pipeline.intelligence.youtube_outlier import annotate_outliers, rank_references
from Thumbnail_Pipeline.intelligence.settings import load_settings

class YouTubeReferenceProvider(Protocol):
    def search(self, query:str, limit:int=12)->list[dict[str,Any]]: ...

def discovery_queries(*,topic:str,category:str)->list[dict[str,str]]:
    q=[]
    if topic.strip(): q.append({"scope":"same_topic","query":topic.strip()})
    if category.strip() and category.strip().lower()!=topic.strip().lower():
        q.append({"scope":"same_category","query":category.strip()})
    return q

def collect_references(*,provider:YouTubeReferenceProvider,topic:str,category:str,limit_per_query:int=12)->list[dict[str,Any]]:
    """Collect cross-channel YouTube references. Provider supplies public search data."""
    seen=set(); out=[]
    for spec in discovery_queries(topic=topic,category=category):
        for item in provider.search(spec["query"],limit=limit_per_query):
            vid=str(item.get("video_id") or "")
            key=vid or (str(item.get("channel_name") or ""),str(item.get("video_title") or ""))
            if key in seen: continue
            seen.add(key)
            out.append({
                "search_scope":spec["scope"],
                "video_id":item.get("video_id"),
                "channel_name":item.get("channel_name"),
                "video_title":item.get("video_title"),
                "thumbnail_url_or_path":item.get("thumbnail_url_or_path"),
                "views":item.get("views"),
                "published_at":item.get("published_at"),
                "topic_match":item.get("topic_match"),
                "category_match":item.get("category_match"),
                "outlier_evidence":item.get("outlier_evidence"),
                "outlier_status":"supported" if item.get("outlier_evidence") else "not_claimed",
            })
    cfg=load_settings(); minimum=int((cfg.get("youtube_reference") or {}).get("minimum_comparison_videos") or 5)
    return rank_references(annotate_outliers(out,minimum_comparison_videos=minimum))

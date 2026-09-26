from __future__ import annotations
from typing import Any, Protocol
import re
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

def _duration_seconds(value:Any)->int|None:
    s=str(value or "").strip()
    m=re.fullmatch(r"P(?:([0-9]+)D)?T(?:([0-9]+)H)?(?:([0-9]+)M)?(?:([0-9]+)S)?",s)
    if not m: return None
    d,h,mi,se=(int(x or 0) for x in m.groups())
    return d*86400+h*3600+mi*60+se

def collect_references(*,provider:YouTubeReferenceProvider,topic:str,category:str,limit_per_query:int=12)->list[dict[str,Any]]:
    """Collect cross-channel YouTube references. Provider supplies public search data."""
    seen=set(); out=[]
    cfg=load_settings(); ref_cfg=cfg.get("youtube_reference") or {}
    min_views=int(ref_cfg.get("minimum_views") or 0)
    exclude_shorter_than=int(ref_cfg.get("exclude_duration_seconds_below") or 0)
    for spec in discovery_queries(topic=topic,category=category):
        for item in provider.search(spec["query"],limit=limit_per_query):
            vid=str(item.get("video_id") or "")
            key=vid or (str(item.get("channel_name") or ""),str(item.get("video_title") or ""))
            if key in seen: continue
            try: views=int(item.get("views") or 0)
            except (TypeError,ValueError): views=0
            duration=_duration_seconds(item.get("duration"))
            if views < min_views: continue
            if exclude_shorter_than and duration is not None and duration < exclude_shorter_than: continue
            seen.add(key)
            out.append({
                "search_scope":spec["scope"],
                "video_id":item.get("video_id"),
                "channel_name":item.get("channel_name"),
                "video_title":item.get("video_title"),
                "thumbnail_url_or_path":item.get("thumbnail_url_or_path"),
                "views":item.get("views"),
                "published_at":item.get("published_at"),
                "duration":item.get("duration"),
                "topic_match":item.get("topic_match"),
                "category_match":item.get("category_match"),
                "outlier_evidence":item.get("outlier_evidence"),
                "outlier_status":"supported" if item.get("outlier_evidence") else "not_claimed",
            })
    minimum=int(ref_cfg.get("minimum_comparison_videos") or 5)
    return rank_references(annotate_outliers(out,minimum_comparison_videos=minimum))

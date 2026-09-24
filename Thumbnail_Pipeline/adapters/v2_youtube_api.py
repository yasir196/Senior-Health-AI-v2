from __future__ import annotations
import urllib.parse
from typing import Any, Callable

class V2YouTubeReferenceProvider:
    """Read-only public YouTube discovery using V2's already-authorized OAuth access token.

    Token acquisition/refresh stays owned by V2. This adapter never stores, copies,
    refreshes, or logs credentials.
    """
    def __init__(self, access_token:str, json_get:Callable[[str,str],dict[str,Any]]|None=None):
        if not access_token: raise ValueError("V2 YouTube OAuth access token is required")
        if json_get is None:
            from youtube_api_sync import _json_get
            json_get=_json_get
        self._token=access_token
        self._get=json_get

    def search(self,query:str,limit:int=12)->list[dict[str,Any]]:
        limit=max(1,min(int(limit),50))
        q=urllib.parse.urlencode({"part":"snippet","type":"video","q":query,"maxResults":limit,"order":"relevance"})
        data=self._get(f"https://www.googleapis.com/youtube/v3/search?{q}",self._token)
        ids=[str((x.get("id") or {}).get("videoId") or "") for x in data.get("items") or []]
        ids=[x for x in ids if x]
        stats={}
        if ids:
            vq=urllib.parse.urlencode({"part":"snippet,statistics","id":",".join(ids),"maxResults":50})
            vd=self._get(f"https://www.googleapis.com/youtube/v3/videos?{vq}",self._token)
            stats={str(x.get("id") or ""):x for x in vd.get("items") or []}
        out=[]
        for item in data.get("items") or []:
            vid=str((item.get("id") or {}).get("videoId") or ""); detail=stats.get(vid,item)
            sn=detail.get("snippet") or item.get("snippet") or {}; th=sn.get("thumbnails") or {}
            best=th.get("maxres") or th.get("standard") or th.get("high") or th.get("medium") or th.get("default") or {}
            st=detail.get("statistics") or {}
            out.append({"video_id":vid,"channel_name":sn.get("channelTitle"),"video_title":sn.get("title"),"thumbnail_url_or_path":best.get("url"),"views":st.get("viewCount"),"published_at":sn.get("publishedAt"),"outlier_evidence":None})
        return out

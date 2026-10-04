from __future__ import annotations
import json, os, urllib.parse
from pathlib import Path
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
            vq=urllib.parse.urlencode({"part":"snippet,statistics,contentDetails","id":",".join(ids),"maxResults":50})
            vd=self._get(f"https://www.googleapis.com/youtube/v3/videos?{vq}",self._token)
            stats={str(x.get("id") or ""):x for x in vd.get("items") or []}
        out=[]
        for item in data.get("items") or []:
            vid=str((item.get("id") or {}).get("videoId") or ""); detail=stats.get(vid,item)
            sn=detail.get("snippet") or item.get("snippet") or {}; th=sn.get("thumbnails") or {}
            best=th.get("maxres") or th.get("standard") or th.get("high") or th.get("medium") or th.get("default") or {}
            st=detail.get("statistics") or {}
            out.append({"video_id":vid,"channel_name":sn.get("channelTitle"),"video_title":sn.get("title"),"thumbnail_url_or_path":best.get("url"),"views":st.get("viewCount"),"published_at":sn.get("publishedAt"),"duration":(detail.get("contentDetails") or {}).get("duration"),"outlier_evidence":None})
        return out


def access_token_from_v2_files_read_only(client_json_path,token_path)->str:
    """Reuse V2 OAuth credentials without calling V2 _access_token, because that function persists refreshed tokens."""
    from youtube_api_sync import _client_config,_read_json,_form_post,GOOGLE_TOKEN_URL
    cfg=_client_config(client_json_path); token=_read_json(token_path)
    refresh=str(token.get("refresh_token") or "").strip()
    if refresh:
        refreshed=_form_post(GOOGLE_TOKEN_URL,{"client_id":cfg["client_id"],"client_secret":cfg["client_secret"],"refresh_token":refresh,"grant_type":"refresh_token"})
        access=str(refreshed.get("access_token") or "").strip()
        if not access: raise RuntimeError("V2 OAuth refresh did not return an access token")
        return access
    access=str(token.get("access_token") or "").strip()
    if not access: raise RuntimeError("V2 YouTube token is missing")
    return access


def discover_v2_youtube_oauth_files_read_only(root:Path|str=".")->tuple[Path|None,Path|None]:
    """Find existing local V2 OAuth JSON files without modifying or exposing their contents."""
    explicit_client=str(os.environ.get("V2_YOUTUBE_CLIENT_JSON") or "").strip()
    explicit_token=str(os.environ.get("V2_YOUTUBE_TOKEN_JSON") or "").strip()
    if explicit_client and explicit_token:
        cp,tp=Path(explicit_client),Path(explicit_token)
        if cp.is_file() and tp.is_file():
            return cp,tp
    base=Path(root).resolve()
    clients=[]; tokens=[]
    skip_parts={".git","Projects","outputs","youtube_assets","__pycache__",".pytest_cache"}
    try:
        candidates=base.rglob("*.json")
        for path in candidates:
            try:
                rel=path.relative_to(base)
                if any(part in skip_parts for part in rel.parts):
                    continue
                if path.stat().st_size>1024*1024:
                    continue
                payload=json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(payload,dict):
                    continue
                cfg=payload.get("installed") or payload.get("web") or {}
                if isinstance(cfg,dict) and cfg.get("client_id") and cfg.get("client_secret"):
                    clients.append(path)
                if payload.get("refresh_token") or payload.get("access_token"):
                    tokens.append(path)
            except Exception:
                continue
    except OSError:
        return None,None
    if not clients or not tokens:
        return None,None
    def rank(path:Path)->tuple[int,int,str]:
        name=path.name.lower()
        return (0 if "youtube" in name else 1,0 if "token" in name or "client" in name else 1,str(path).lower())
    clients.sort(key=rank); tokens.sort(key=rank)
    return clients[0],tokens[0]

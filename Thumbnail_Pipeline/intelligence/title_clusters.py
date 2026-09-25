from __future__ import annotations
import math, re
from collections import Counter
from typing import Any
from Thumbnail_Pipeline.intelligence.settings import load_settings

_STOP={"the","a","an","and","or","of","to","in","on","for","with","your","you","this","that","is","are"}

def _tokens(text: str) -> list[str]:
    return [x for x in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(x)>1 and x not in _STOP]

def _vectors(titles: list[str]) -> list[dict[str,float]]:
    docs=[_tokens(t) for t in titles]; df=Counter()
    for d in docs: df.update(set(d))
    n=max(1,len(docs)); out=[]
    for d in docs:
        tf=Counter(d); v={}
        for term,count in tf.items():
            v[term]=float(count)*(math.log((n+1)/(df[term]+1))+1.0)
        norm=math.sqrt(sum(x*x for x in v.values())) or 1.0
        out.append({k:x/norm for k,x in v.items()})
    return out

def _cos(a: dict[str,float], b: dict[str,float]) -> float:
    if len(a)>len(b): a,b=b,a
    return sum(v*b.get(k,0.0) for k,v in a.items())

def discover_title_clusters(rows: list[dict[str,Any]], similarity_threshold: float|None=None) -> dict[str,Any]:
    """Discover title clusters from historical evidence. No semantic category names are seeded."""
    if similarity_threshold is None:
        cfg=load_settings().get("title_clustering") or {}
        similarity_threshold=float(cfg["similarity_threshold"])
    usable=[r for r in rows if str((r.get("performance") or {}).get("title") or "").strip()]
    titles=[str((r.get("performance") or {}).get("title") or "") for r in usable]
    vecs=_vectors(titles); parent=list(range(len(usable)))
    def find(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]]; x=parent[x]
        return x
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b: parent[b]=a
    for i in range(len(vecs)):
        for j in range(i):
            if _cos(vecs[i],vecs[j])>=similarity_threshold: union(i,j)
    groups={}
    for i in range(len(usable)): groups.setdefault(find(i),[]).append(i)
    ordered=sorted(groups.values(), key=lambda g:(-len(g), min(g)))
    clusters=[]
    for num,idxs in enumerate(ordered,1):
        cid=f"cluster_{num:03d}"
        centroid={}
        for i in idxs:
            for k,v in vecs[i].items(): centroid[k]=centroid.get(k,0.0)+v/len(idxs)
        clusters.append({"cluster_id":cid,"member_count":len(idxs),"member_indexes":idxs,
                         "centroid":centroid,"example_titles":[titles[i] for i in idxs[:5]]})
    return {"method":"tfidf_title_similarity_connected_components","similarity_threshold":similarity_threshold,
            "clusters":clusters,"rows":usable}

def assign_title_cluster(title: str, discovered: dict[str,Any], minimum_similarity: float|None=None) -> dict[str,Any]|None:
    rows=discovered.get("rows") or []; clusters=discovered.get("clusters") or []
    if not rows or not clusters: return None
    historical=[str((r.get("performance") or {}).get("title") or "") for r in rows]
    all_vecs=_vectors(historical+[title]); q=all_vecs[-1]
    best=None
    for c in clusters:
        idxs=c["member_indexes"]
        score=max((_cos(q,all_vecs[i]) for i in idxs),default=0.0)
        candidate=(score,c["member_count"],c["cluster_id"],c)
        if best is None or candidate[:3]>best[:3]: best=candidate
    if best is None: return None
    threshold=float(discovered.get("similarity_threshold") if minimum_similarity is None else minimum_similarity)
    if best[0] < threshold:
        return {"cluster_id":None,"status":"unmatched","similarity":round(best[0],6),
                "minimum_similarity":threshold,"nearest_cluster_id":best[2],
                "nearest_example_titles":best[3]["example_titles"],"member_indexes":[]}
    return {"cluster_id":best[2],"status":"matched","similarity":round(best[0],6),
            "minimum_similarity":threshold,"member_count":best[1],
            "example_titles":best[3]["example_titles"],"member_indexes":best[3]["member_indexes"]}

from __future__ import annotations
import json, sqlite3
from pathlib import Path
from typing import Any

def persist_title_clusters(db_path: Path, discovered: dict[str,Any], source_run_id: int|None=None) -> None:
    """Persist derived thumbnail intelligence only inside Thumbnail_Pipeline-owned DB."""
    path=Path(db_path); path.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(path) as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS title_clusters(
          cluster_id TEXT PRIMARY KEY, method TEXT NOT NULL, similarity_threshold REAL NOT NULL,
          member_count INTEGER NOT NULL, example_titles_json TEXT NOT NULL, source_run_id INTEGER);
        CREATE TABLE IF NOT EXISTS title_cluster_members(
          cluster_id TEXT NOT NULL, asset_id TEXT NOT NULL, title TEXT NOT NULL,
          ctr REAL, impressions REAL, thumbnail_text TEXT,
          PRIMARY KEY(cluster_id,asset_id));
        """)
        con.execute("DELETE FROM title_cluster_members"); con.execute("DELETE FROM title_clusters")
        rows=discovered.get("rows") or []
        for c in discovered.get("clusters") or []:
            con.execute("INSERT INTO title_clusters VALUES(?,?,?,?,?,?)",
                (c["cluster_id"],discovered["method"],discovered["similarity_threshold"],c["member_count"],
                 json.dumps(c["example_titles"],ensure_ascii=False),source_run_id))
            for i in c["member_indexes"]:
                r=rows[i]; perf=r.get("performance") or {}; ocr=r.get("ocr") or {}
                con.execute("INSERT INTO title_cluster_members VALUES(?,?,?,?,?,?)",
                    (c["cluster_id"],str(r.get("asset_id") or i),str(perf.get("title") or ""),
                     perf.get("ctr"),perf.get("impressions"),ocr.get("text")))

import sqlite3
from Thumbnail_Pipeline.intelligence.title_clusters import discover_title_clusters,assign_title_cluster
from Thumbnail_Pipeline.db.cluster_store import persist_title_clusters

def row(asset,title,text=""):
    return {"asset_id":asset,"performance":{"title":title,"ctr":5.0,"impressions":2000},"ocr":{"text":text},"v2_analysis":{}}

def test_clusters_are_discovered_from_titles_not_named_categories():
    rows=[row("1","Coffee Every Morning Here's What Happens"),row("2","Tea Every Morning Here's What Happens"),row("3","Chair Exercise for Stronger Legs")]
    d=discover_title_clusters(rows,similarity_threshold=.2)
    assert all(c["cluster_id"].startswith("cluster_") for c in d["clusters"])
    a=assign_title_cluster("Clove in Coffee Every Morning Here's What Happens",d)
    assert a and a["cluster_id"]==d["clusters"][0]["cluster_id"]

def test_cluster_store_is_pipeline_owned_derived_schema(tmp_path):
    d=discover_title_clusters([row("1","Coffee Every Morning"),row("2","Tea Every Morning")],similarity_threshold=.1)
    db=tmp_path/"thumbnail_intelligence.db"; persist_title_clusters(db,d,10)
    with sqlite3.connect(db) as con:
        assert con.execute("select count(*) from title_clusters").fetchone()[0]>=1
        assert con.execute("select count(*) from title_cluster_members").fetchone()[0]==2


def test_weak_title_is_unmatched_instead_of_force_fit():
    rows=[row("1","Coffee Every Morning Here's What Happens"),row("2","Tea Every Morning Here's What Happens"),row("3","Chair Exercise for Stronger Legs")]
    d=discover_title_clusters(rows,similarity_threshold=.24)
    a=assign_title_cluster("Understanding Medicare Enrollment Deadlines",d)
    assert a is not None
    assert a["status"]=="unmatched"
    assert a["cluster_id"] is None
    assert a["member_indexes"]==[]
    assert a["nearest_cluster_id"].startswith("cluster_")

def test_match_reports_threshold_and_status():
    rows=[row("1","Coffee Every Morning Here's What Happens"),row("2","Tea Every Morning Here's What Happens")]
    d=discover_title_clusters(rows,similarity_threshold=.2)
    a=assign_title_cluster("Clove Coffee Every Morning Here's What Happens",d)
    assert a["status"]=="matched"
    assert a["similarity"]>=a["minimum_similarity"]


def test_cluster_ids_are_stable_when_input_order_changes():
    rows=[row("a","Coffee Every Morning Here's What Happens"),row("b","Tea Every Morning Here's What Happens"),row("c","Chair Exercise for Stronger Legs")]
    first=discover_title_clusters(rows,similarity_threshold=.2)
    second=discover_title_clusters(list(reversed(rows)),similarity_threshold=.2)
    def signatures(d):
        return {frozenset(d["rows"][i]["asset_id"] for i in c["member_indexes"]):c["cluster_id"] for c in d["clusters"]}
    assert signatures(first)==signatures(second)

def test_cluster_store_persists_source_run_id(tmp_path):
    d=discover_title_clusters([row("1","Coffee Every Morning"),row("2","Tea Every Morning")],similarity_threshold=.1)
    db=tmp_path/"thumbnail_intelligence.db"; persist_title_clusters(db,d,42)
    with sqlite3.connect(db) as con:
        assert {r[0] for r in con.execute("select source_run_id from title_clusters")}=={42}

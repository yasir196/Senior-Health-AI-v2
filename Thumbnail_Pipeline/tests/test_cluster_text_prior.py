from Thumbnail_Pipeline.intelligence.cluster_prior import eligible_cluster_winners
from Thumbnail_Pipeline.intelligence.text_mechanisms import discover_text_mechanisms,title_bound_text_candidates

def r(title,text,ctr,imp=2000):
    return {"performance":{"title":title,"ctr":ctr,"impressions":imp,"attribution_status":""},"ocr":{"text":text}}

def test_cluster_prior_excludes_lower_half_from_positive_seed():
    rows=[r("A","OLD LOW",1),r("B","OLD MID",3),r("C","OLD HIGH",5)]
    x=eligible_cluster_winners(rows)
    assert [z["ocr"]["text"] for z in x["winner_rows"]]==["OLD MID","OLD HIGH"]

def test_fresh_candidates_never_copy_historical_subject_words():
    winners=[r("Banana at Night","TRUTH ABOUT BANANA",5),r("Peanut Butter Daily","PEANUT BUTTER INSIDE YOU",6)]
    m=discover_text_mechanisms(winners)
    out=title_bound_text_candidates("1 CLOVE in Your Coffee Every Morning Here's What Happens",m)
    joined=" ".join(out)
    assert "BANANA" not in joined and "PEANUT" not in joined and "BUTTER" not in joined
    title_words=set("1 CLOVE in Your Coffee Every Morning Here's What Happens".upper().replace("'","").split())
    assert all(set(x.replace("'","").split())<=title_words for x in out)

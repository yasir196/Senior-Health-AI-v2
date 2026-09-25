from Thumbnail_Pipeline.intelligence.cluster_prior import eligible_cluster_winners
from Thumbnail_Pipeline.intelligence.text_mechanisms import discover_text_mechanisms,transformation_text_candidates,constraint_text_candidates

def r(title,text,ctr,imp=2000):
    return {"performance":{"title":title,"ctr":ctr,"impressions":imp,"attribution_status":""},"ocr":{"text":text}}

def test_cluster_prior_excludes_lower_half_from_positive_seed():
    rows=[r("A","OLD LOW",1),r("B","OLD MID",3),r("C","OLD HIGH",5)]
    x=eligible_cluster_winners(rows)
    assert [z["ocr"]["text"] for z in x["winner_rows"]]==["OLD MID","OLD HIGH"]

def test_fresh_candidates_do_not_copy_historical_subjects():
    winners=[r("Banana at Night","TRUTH ABOUT BANANA",5),r("Peanut Butter Daily","TRUTH ABOUT PEANUT BUTTER",6)]
    m=discover_text_mechanisms(winners)
    out=transformation_text_candidates("1 CLOVE in Your Coffee Every Morning Here's What Happens",m)
    joined=" ".join(out)
    assert "BANANA" not in joined and "PEANUT" not in joined and "BUTTER" not in joined

def test_literal_hook_vocabulary_comes_from_observed_winner_not_code_seed():
    winners=[r("Banana at Night","TRUTH ABOUT BANANA",5),r("Milk at Night","TRUTH ABOUT MILK",6)]
    m=discover_text_mechanisms(winners)
    out=transformation_text_candidates("Clove in Coffee Every Morning",m)
    assert out
    assert "TRUTH ABOUT" in out[0]
    literals={x for p in m["patterns"] for x in p["skeleton"] if x!="<TITLE>"}
    assert {"truth","about"}<=literals

def test_no_observed_transformation_means_no_invented_hook():
    m=discover_text_mechanisms([])
    assert transformation_text_candidates("Clove in Coffee Every Morning",m)==[]


def test_candidates_are_ranked_and_auditable_without_seeded_hook_list():
    winners=[r("Banana at Night","TRUTH ABOUT BANANA",5),r("Milk at Night","TRUTH ABOUT MILK",6)]
    m=discover_text_mechanisms(winners)
    out=transformation_text_candidates("Clove in Coffee Every Morning",m,with_audit=True)
    assert out and all(x["audit"]["valid"] for x in out)
    assert out==sorted(out,key=lambda x:(x["score"],x["text"]),reverse=True)

def test_candidate_filter_rejects_vocabulary_not_in_title_or_discovered_pattern():
    from Thumbnail_Pipeline.intelligence.text_mechanisms import _candidate_score
    m=discover_text_mechanisms([r("Banana at Night","TRUTH ABOUT BANANA",5),r("Milk at Night","TRUTH ABOUT MILK",6)])
    score,audit=_candidate_score("SECRET CLOVE","Clove in Coffee",m)
    assert score<0 and audit["reason"]=="unsupported_vocabulary"


def test_one_off_cluster_overlay_is_not_promoted_as_reusable_rule():
    m=discover_text_mechanisms([r("Banana at Night","INSIDE YOU?",5)])
    assert transformation_text_candidates("Clove in Coffee Every Morning",m)==[]

def test_recurrent_transformation_remains_eligible():
    m=discover_text_mechanisms([r("Banana at Night","TRUTH ABOUT BANANA",5),r("Milk at Night","TRUTH ABOUT MILK",6)])
    out=transformation_text_candidates("Clove in Coffee Every Morning",m)
    assert out and "TRUTH ABOUT" in out[0]


def test_constraint_fallback_uses_only_current_title_words():
    winners=[r("Banana at Night","INSIDE YOU?",5),r("Milk at Night","NIGHT CUP?",6)]
    m=discover_text_mechanisms(winners)
    out=constraint_text_candidates("1 CLOVE in Your Coffee Every Morning",m,with_audit=True)
    assert out
    title_words={"1","clove","in","your","coffee","every","morning"}
    for item in out:
        assert set(item["text"].lower().rstrip("?").split())<=title_words
        assert item["audit"]["source"]=="constraint_fallback"

def test_constraint_fallback_does_not_copy_historical_subject_words():
    winners=[r("Banana at Night","INSIDE YOU?",5),r("Milk at Night","NIGHT CUP?",6)]
    m=discover_text_mechanisms(winners)
    joined=" ".join(constraint_text_candidates("1 CLOVE in Your Coffee Every Morning",m))
    assert "BANANA" not in joined and "MILK" not in joined

def test_constraint_fallback_prefers_title_distinctive_tokens_without_seed_list():
    winners=[r("Banana Every Morning","BANANA?",5),r("Milk Every Morning","MILK?",6)]
    m=discover_text_mechanisms(winners)
    out=constraint_text_candidates("1 CLOVE in Your Coffee Every Morning",m)
    assert out and "CLOVE" in out[0]

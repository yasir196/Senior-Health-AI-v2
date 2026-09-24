from Thumbnail_Pipeline.intelligence.text_psychology import discover_text_patterns,pattern_word_map

def row(text,ctr=5,imp=5000,category="mobility"):
    return {"performance":{"title":"T","ctr":ctr,"impressions":imp},"ocr":{"text":text},"v2_analysis":{"hero_category":category}}

def test_patterns_are_discovered_not_seeded():
    d=discover_text_patterns([row("DO THIS FIRST"),row("DO THIS FIRST",7)])
    names={x["discovered_pattern"] for x in d["patterns"]}
    assert "do this first" in names
    assert "[ACTION]" not in names and "[COMMAND]" not in names

def test_word_map_preserves_unclassified_tokens():
    m=pattern_word_map("WHAT HAPPENS NEXT?",[])
    assert [x["token"] for x in m][:3]==["WHAT","HAPPENS","NEXT"]
    assert all(x["status"]=="unclassified" for x in m)

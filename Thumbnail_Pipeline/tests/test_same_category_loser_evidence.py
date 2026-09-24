from Thumbnail_Pipeline.intelligence.recommendations import build_loser_suggestions

def row(category,title,text,ctr):
    return {"performance":{"title":title,"ctr":ctr,"impressions":5000},"ocr":{"text":text},"v2_analysis":{"hero_category":category}}

def test_loser_only_receives_same_category_winner_evidence():
    loser=row("mobility","L","LOW",2)
    winners=[row("mobility","M","MOVE",7),row("nutrition","N","EAT",8)]
    result=build_loser_suggestions([loser],winners)["suggestions"][0]["suggestion_for_loser"]["same_category_winner_evidence"]
    assert [x["title"] for x in result]==["M"]

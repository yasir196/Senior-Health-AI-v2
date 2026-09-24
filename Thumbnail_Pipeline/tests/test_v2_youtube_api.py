from Thumbnail_Pipeline.adapters.v2_youtube_api import V2YouTubeReferenceProvider

def test_reuses_token_without_own_credentials():
    calls=[]
    def fake(url,token):
        calls.append((url,token))
        if "/search?" in url:
            return {"items":[{"id":{"videoId":"abc"},"snippet":{"title":"T","channelTitle":"C"}}]}
        return {"items":[{"id":"abc","snippet":{"title":"T","channelTitle":"C","thumbnails":{"high":{"url":"thumb"}}},"statistics":{"viewCount":"123"}}]}
    p=V2YouTubeReferenceProvider("existing-v2-token",json_get=fake)
    rows=p.search("mobility")
    assert rows[0]["thumbnail_url_or_path"]=="thumb"
    assert all(token=="existing-v2-token" for _,token in calls)

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


def test_read_only_oauth_refresh_never_calls_save_token(monkeypatch,tmp_path):
    import sys,types
    fake=types.ModuleType("youtube_api_sync")
    fake.GOOGLE_TOKEN_URL="https://oauth.example/token"
    fake._client_config=lambda p:{"client_id":"id","client_secret":"secret"}
    fake._read_json=lambda p:{"refresh_token":"refresh"}
    fake._form_post=lambda url,data:{"access_token":"memory-only"}
    fake._save_token=lambda *a,**k: (_ for _ in ()).throw(AssertionError("must not persist token"))
    monkeypatch.setitem(sys.modules,"youtube_api_sync",fake)
    from Thumbnail_Pipeline.adapters.v2_youtube_api import access_token_from_v2_files_read_only
    assert access_token_from_v2_files_read_only(tmp_path/"client.json",tmp_path/"token.json")=="memory-only"

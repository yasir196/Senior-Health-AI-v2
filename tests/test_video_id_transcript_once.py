from pathlib import Path
import pandas as pd
from analytics_db import init_db, bulk_import_channel_content_csv, list_videos, register_youtube_only_video, snapshot_timestamped_transcript, needs_transcript_upload


def test_content_column_video_id_is_saved(tmp_path: Path):
    db=tmp_path/'db.sqlite'; init_db(db)
    df=pd.DataFrame([
        {'Content':'dQw4w9WgXcQ','Video title':'Real Title','Views':100,'Average view duration':'5:00','Average percentage viewed (%)':30,'Impressions':1000,'Impressions click-through rate (%)':6.0},
        {'Content':'Total','Video title':'','Views':100}
    ])
    r=bulk_import_channel_content_csv(db,df,source_file='content.csv')
    vids=list_videos(db)
    assert r['imported_videos']==1
    assert len(vids)==1
    assert vids[0]['youtube_video_id']=='dQw4w9WgXcQ'
    assert vids[0]['youtube_title']=='Real Title'


def test_transcript_is_requested_once(tmp_path: Path):
    db=tmp_path/'db.sqlite'; init_db(db)
    aid=register_youtube_only_video(db,title='Old Video',youtube_video_id='abc123DEF45')
    assert needs_transcript_upload(db,aid) is True
    transcript='[00:00:00] hello\n[00:00:03] world'
    snapshot_timestamped_transcript(db,aid,transcript)
    assert needs_transcript_upload(db,aid) is False

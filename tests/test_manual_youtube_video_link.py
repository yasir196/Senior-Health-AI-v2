import json
from pathlib import Path
from analytics_db import ensure_project_record, register_youtube_only_video, bind_youtube_video_id_to_project, get_video, list_videos, AnalyticsDBError


def make_project(tmp_path, pid='p1', title='Internal SEO Title'):
    p = tmp_path / 'Projects' / pid
    p.mkdir(parents=True)
    (p/'project.json').write_text(json.dumps({'project_id':pid,'anchor_title':title}), encoding='utf-8')
    return p


def test_manual_id_binding_does_not_need_title_match(tmp_path):
    db=tmp_path/'Analytics'/'db.sqlite'; p=make_project(tmp_path)
    aid=ensure_project_record(db,p)
    bind_youtube_video_id_to_project(db,aid,'RItFbOZinFA')
    row=get_video(db,aid)
    assert row['youtube_video_id']=='RItFbOZinFA'
    assert row['source_type']=='project_linked'


def test_manual_binding_merges_existing_youtube_only_staging_row(tmp_path):
    db=tmp_path/'Analytics'/'db.sqlite'; p=make_project(tmp_path, title='Completely Different Internal Title')
    aid=ensure_project_record(db,p)
    staged=register_youtube_only_video(db,title='Public Changed Title',youtube_video_id='RItFbOZinFA')
    assert staged != aid
    out=bind_youtube_video_id_to_project(db,aid,'RItFbOZinFA')
    assert out==aid
    rows=list_videos(db)
    assert not any(v['analytics_id']==staged for v in rows)
    assert get_video(db,aid)['youtube_video_id']=='RItFbOZinFA'


def test_video_id_cannot_be_bound_to_two_projects(tmp_path):
    db=tmp_path/'Analytics'/'db.sqlite'; a=ensure_project_record(db,make_project(tmp_path,'a')); b=ensure_project_record(db,make_project(tmp_path,'b'))
    bind_youtube_video_id_to_project(db,a,'RItFbOZinFA')
    try:
        bind_youtube_video_id_to_project(db,b,'RItFbOZinFA')
    except AnalyticsDBError:
        pass
    else:
        raise AssertionError('duplicate YouTube ID must be blocked')

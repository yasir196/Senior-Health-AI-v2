from pathlib import Path
from analytics_db import (
    init_db, register_youtube_only_video, needs_transcript_upload,
    snapshot_timestamped_transcript
)

def test_transcript_helper_exists_and_flips_after_snapshot(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    init_db(db)
    aid = register_youtube_only_video(db, title="Old Video")
    assert needs_transcript_upload(db, aid) is True

    snapshot_timestamped_transcript(
        db,
        aid,
        "[00:00:00] hello\n[00:00:03] next point"
    )
    assert needs_transcript_upload(db, aid) is False

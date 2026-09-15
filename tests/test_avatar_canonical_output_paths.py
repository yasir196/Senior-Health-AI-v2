from pathlib import Path
import json
import avatar_timing


def test_transcripts_are_written_to_selected_project_avatar_transcripts(tmp_path: Path):
    project = tmp_path / "selected-project"
    project.mkdir()
    transcript_dir = project / "avatar_transcripts"
    transcript_dir.mkdir(parents=True, exist_ok=True)

    p = transcript_dir / "c1.json"
    avatar_timing._write_text_path_safe(p, json.dumps({"text":"hello"}) + "\n")
    assert p.is_file()
    assert p.parent == project / "avatar_transcripts"


def test_timeline_files_are_project_local(tmp_path: Path):
    project = tmp_path / "selected-project"
    project.mkdir()
    for name in ("08_actual_timeline.csv", "avatar_timing_manifest.json", "avatar_alignment_report.md"):
        p = project / name
        avatar_timing._write_text_path_safe(p, "x\n")
        assert p.is_file()
        assert p.parent == project

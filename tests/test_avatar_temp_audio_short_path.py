from pathlib import Path
import tempfile
import avatar_timing


def test_temp_audio_uses_short_os_temp_not_project_tree(tmp_path: Path):
    deep = tmp_path
    for i in range(8):
        deep = deep / ("very-long-project-folder-" + str(i) + "-" + ("x" * 25))
    transcript_dir = deep / "avatar_transcripts"

    temp_dir = avatar_timing._avatar_temp_audio_dir(transcript_dir, {})

    assert "_temp_audio" not in str(temp_dir)
    assert str(temp_dir).startswith(str(Path(tempfile.gettempdir())))
    assert temp_dir.parent.name == "SHAI_avatar_audio"
    assert temp_dir.is_dir()


def test_temp_audio_directory_is_stable_per_project(tmp_path: Path):
    transcript_dir = tmp_path / "project" / "avatar_transcripts"
    first = avatar_timing._avatar_temp_audio_dir(transcript_dir, {})
    second = avatar_timing._avatar_temp_audio_dir(transcript_dir, {})
    assert first == second


def test_configured_temp_root_is_supported(tmp_path: Path):
    transcript_dir = tmp_path / "project" / "avatar_transcripts"
    custom = tmp_path / "short_temp"
    result = avatar_timing._avatar_temp_audio_dir(
        transcript_dir, {"avatar_transcription_temp_root": str(custom)}
    )
    assert result.parent == custom
    assert result.is_dir()

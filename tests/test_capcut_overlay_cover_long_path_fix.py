from pathlib import Path
import capcut_export


def test_subdraft_cover_uses_long_safe_mkdir(tmp_path, monkeypatch):
    source = tmp_path / "cover.jpg"
    source.write_bytes(b"cover")
    destination = tmp_path / "deep" / "subdraft" / "UUID" / "draft_cover.jpg"

    called = {"mkdir": 0}
    real_mkdir = capcut_export._mkdir_long_safe

    def checked_mkdir(path):
        called["mkdir"] += 1
        return real_mkdir(path)

    monkeypatch.setattr(capcut_export, "_mkdir_long_safe", checked_mkdir)
    capcut_export._copy_subdraft_cover(source, destination)

    assert called["mkdir"] == 1
    assert destination.is_file()
    assert destination.read_bytes() == b"cover"

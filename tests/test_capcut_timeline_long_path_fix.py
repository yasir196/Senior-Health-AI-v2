import json
from pathlib import Path
import capcut_export

def test_write_json_uses_long_safe_mkdir_for_timeline_mirror(tmp_path, monkeypatch):
    target = tmp_path / "CapCut_Project" / "Timelines" / "ed722584-c8ae-5592-bceb-3c56bc7b8e25" / "draft_content.json"
    calls = []
    real_mkdir = capcut_export._mkdir_long_safe

    def checked_mkdir(path):
        calls.append(Path(path))
        return real_mkdir(path)

    monkeypatch.setattr(capcut_export, "_mkdir_long_safe", checked_mkdir)
    capcut_export._write_json(target, {"timeline_id": "test"})

    assert calls == [target.parent]
    assert target.is_file()
    assert json.loads(target.read_text(encoding="utf-8"))["timeline_id"] == "test"

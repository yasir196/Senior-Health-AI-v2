from pathlib import Path
import pytest
from Thumbnail_Pipeline.analyzer.batch import analyze_folder

def test_batch_rejects_output_escape(tmp_path):
    with pytest.raises(ValueError):
        analyze_folder(tmp_path, Path("../../outside.jsonl"), Path("../../outside.csv"))

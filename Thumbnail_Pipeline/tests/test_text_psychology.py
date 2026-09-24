from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from Thumbnail_Pipeline.intelligence.text_psychology import pattern_sequence, psychology_tags


def test_problem_action_command_is_explicit():
    seq = pattern_sequence("KNEE PAIN? DO THIS FIRST")
    assert "[PROBLEM]" in seq
    assert "[ACTION]" in seq
    assert "[COMMAND]" in seq


def test_curiosity_question_pattern():
    tags = psychology_tags("WHAT HAPPENS NEXT?")
    assert "question" in tags
    assert "curiosity" in tags

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
PROJECTS_DIR = ROOT / "Projects"
DYNAMIC_STRATEGY_PATH = ROOT / "Templates" / "Dynamic" / "outline_strategy.json"

DYNAMIC_OUTPUTS = (
    ("Dynamic Outline", "Dynamic_05_script_outline.md"),
    ("Dynamic Writer Prompt", "Dynamic_05_writer_prompt.md"),
    ("Dynamic Final Script", "Dynamic_06_final_script.md"),
)


def _project_names() -> list[str]:
    if not PROJECTS_DIR.is_dir():
        return []
    return sorted(
        [item.name for item in PROJECTS_DIR.iterdir() if item.is_dir()],
        key=str.casefold,
    )


def _strategy_summary() -> tuple[bool, str]:
    if not DYNAMIC_STRATEGY_PATH.is_file():
        return False, "Dynamic outline strategy JSON is missing."
    try:
        payload = json.loads(DYNAMIC_STRATEGY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"Dynamic outline strategy JSON could not be read: {exc}"
    blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        return False, "Dynamic outline strategy JSON has no valid blocks list."
    enabled = sum(1 for block in blocks if isinstance(block, dict) and block.get("enabled", True))
    return True, f"Strategy loaded · {len(blocks)} parent block(s) · {enabled} enabled"


st.set_page_config(page_title="DW Flow", page_icon="🧩", layout="wide")
st.title("DW Flow")
st.caption(
    "Separate Dynamic workflow. The existing Workflow, Outline, Opus Writer Prompt, and old outputs are not used or modified by this page."
)

ok, strategy_message = _strategy_summary()
if ok:
    st.success(strategy_message)
else:
    st.warning(strategy_message)

projects = _project_names()
if not projects:
    st.info("No project folders are available yet.")
    st.stop()

project_name = st.selectbox("Project", projects, key="dw_flow_project")
project = PROJECTS_DIR / project_name

st.markdown("### Dynamic workflow")
for index, (label, filename) in enumerate(DYNAMIC_OUTPUTS, 1):
    path = project / filename
    with st.container(border=True):
        left, right = st.columns([3, 1])
        left.markdown(f"**{index}. {label}**")
        left.code(filename, language=None)
        if path.is_file():
            right.success("READY")
        else:
            right.info("PENDING")

st.info(
    "DW Flow is currently an isolated workflow shell only. No Dynamic generation action is connected yet. "
    "Generation logic will be added separately so the old pipeline remains untouched."
)

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


def _load_strategy() -> tuple[dict | None, str]:
    """Load the Outline Builder JSON used by the DW Flow Dynamic Outline."""
    if not DYNAMIC_STRATEGY_PATH.is_file():
        return None, "Dynamic outline strategy JSON is missing."
    try:
        payload = json.loads(DYNAMIC_STRATEGY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"Dynamic outline strategy JSON could not be read: {exc}"
    blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        return None, "Dynamic outline strategy JSON has no valid blocks list."
    enabled = sum(1 for block in blocks if isinstance(block, dict) and block.get("enabled", True))
    return payload, f"Strategy loaded · {len(blocks)} parent block(s) · {enabled} enabled"


def _enabled_structure(payload: dict) -> list[dict]:
    """Return the authoritative enabled parent/child order without changing the saved JSON."""
    structure: list[dict] = []
    for parent in payload.get("blocks", []):
        if not isinstance(parent, dict) or not parent.get("enabled", True):
            continue
        children = [
            child
            for child in parent.get("children", [])
            if isinstance(child, dict) and child.get("enabled", True)
        ]
        structure.append({"parent": parent, "children": children})
    return structure


st.set_page_config(page_title="DW Flow", page_icon="🧩", layout="wide")
st.title("DW Flow")
st.caption(
    "Separate Dynamic workflow. The existing Workflow, Outline, Opus Writer Prompt, and old outputs are not used or modified by this page."
)

strategy, strategy_message = _load_strategy()
if strategy is not None:
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
        if label == "Dynamic Outline":
            if strategy is None:
                right.warning("NO STRATEGY")
            else:
                right.success("JSON CONNECTED")
                left.caption("Structure source: Templates/Dynamic/outline_strategy.json")
        elif path.is_file():
            right.success("READY")
        else:
            right.info("PENDING")

if strategy is not None:
    st.markdown("### Dynamic Outline · connected structure")
    st.caption(
        "This is the exact enabled parent/child order currently supplied by Outline Builder JSON to the DW Flow Dynamic Outline. "
        "Disabled blocks stay saved in JSON but are not part of the active outline structure."
    )
    structure = _enabled_structure(strategy)
    if not structure:
        st.info("The JSON is connected, but there are no enabled parent blocks yet.")
    else:
        for number, item in enumerate(structure, 1):
            parent = item["parent"]
            parent_name = str(parent.get("name") or f"Parent {number}").strip()
            with st.expander(f"{number}. {parent_name}", expanded=True):
                instruction = str(parent.get("instruction") or "").strip()
                if instruction:
                    st.write(instruction)
                repeat = parent.get("repeat") if isinstance(parent.get("repeat"), dict) else {}
                if repeat.get("enabled"):
                    st.caption(f"Repeat: {repeat.get('mode', 'seconds')} · {repeat.get('value', '') or repeat.get('positions', '')}")
                children = item["children"]
                if children:
                    for child_number, child in enumerate(children, 1):
                        child_name = str(child.get("name") or f"Child {child_number}").strip()
                        child_instruction = str(child.get("instruction") or "").strip()
                        st.markdown(f"**{number}.{child_number} {child_name}**")
                        if child_instruction:
                            st.write(child_instruction)
                        child_repeat = child.get("repeat") if isinstance(child.get("repeat"), dict) else {}
                        if child_repeat.get("enabled"):
                            st.caption(
                                f"Repeat: {child_repeat.get('mode', 'seconds')} · "
                                f"{child_repeat.get('value', '') or child_repeat.get('positions', '')}"
                            )
                else:
                    st.caption("No enabled child blocks.")

st.info(
    "Only the Outline Builder JSON has been connected to the DW Flow Dynamic Outline at this stage. "
    "No Writer, Final Script, old Workflow, old Outline, or Opus Writer logic is changed or connected here."
)

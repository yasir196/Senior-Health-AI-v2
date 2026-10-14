from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from v31_core import detect_codex_template, run_codex

ROOT = Path(__file__).resolve().parents[1]
PROJECTS_DIR = ROOT / "Projects"
DYNAMIC_STRATEGY_PATH = ROOT / "Templates" / "Dynamic" / "outline_strategy.json"
CONFIG_PATH = ROOT / "config.json"
RUN_LOG_DIR = ROOT / "RunLogs"
DYNAMIC_OUTLINE_FILENAME = "Dynamic_05_script_outline.md"

DYNAMIC_OUTPUTS = (
    ("Dynamic Outline", DYNAMIC_OUTLINE_FILENAME),
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


def _load_config() -> dict:
    try:
        payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _dynamic_outline_prompt(project: Path, strategy: dict) -> str:
    """Build a generic runtime prompt; creative structure comes only from current JSON."""
    strategy_json = json.dumps(strategy, indent=2, ensure_ascii=False)
    return f"""You are the Dynamic Outline Generator for the separate DW Flow.

PROJECT DIRECTORY:
{project}

OUTPUT FILE:
{DYNAMIC_OUTLINE_FILENAME}

DYNAMIC STRATEGY — AUTHORITATIVE USER CONTROL PLANE:
{strategy_json}

TASK:
Create the project's Dynamic script outline and write ONLY the finished outline to {DYNAMIC_OUTLINE_FILENAME} inside the project directory.

DYNAMIC INTERPRETATION RULES:
- Treat the supplied JSON as the authoritative creative structure for this run.
- Interpret block names semantically at runtime. No block name has a built-in meaning.
- Do not assume or require Hook, Main Body, Conclusion, CTA, Evidence, Story, or any other named section unless the current JSON requests it.
- Follow enabled parent blocks in their saved JSON order.
- Within each enabled parent, follow enabled child blocks in their saved JSON order.
- Follow each block's natural-language instruction as written.
- Disabled blocks are not part of the active outline.
- If repeat.enabled is true, interpret its mode/value/positions dynamically. For ai_natural, choose natural placements using the block instruction and project evidence rather than inventing a fixed cadence.
- A block may have any user-created name. Never replace an unfamiliar block with a hardcoded template section.
- Do not add a hidden standard outline structure around the JSON structure.
- JSON controls creative organization; project evidence controls factual content. Never invent evidence to satisfy a block.

PROJECT EVIDENCE:
Use the current project's available research/medical/source artifacts as factual grounding. Read relevant project files directly from the project directory. If a requested block cannot be supported by available project evidence, make that limitation explicit in the outline rather than fabricating support.

ISOLATION:
- Do not modify old-pipeline files.
- Do not create or overwrite 05_script_outline.md, opus_writer_package.md, or 06_final_script.md.
- Do not modify Templates/Dynamic/outline_strategy.json.
- The only requested generated artifact is {DYNAMIC_OUTLINE_FILENAME}.

OUTPUT:
Write a useful writer-facing Markdown outline. Preserve the current JSON's semantic hierarchy and order. Do not include process commentary before or after the outline.
"""


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
            elif path.is_file() and path.stat().st_size > 0:
                right.success("READY · JSON CONNECTED")
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

    st.markdown("### Generate Dynamic Outline")
    st.caption(
        "The generator reads the current JSON at run time. Creative block names and section structure are not hardcoded in DW Flow."
    )
    config = _load_config()
    codex_template = detect_codex_template(config)
    can_generate = bool(structure) and bool(codex_template)
    if not codex_template:
        st.warning("Direct Codex command is not configured/available, so Dynamic Outline generation cannot run yet.")
    if st.button(
        "Generate Dynamic Outline",
        type="primary",
        disabled=not can_generate,
        key="dw_generate_dynamic_outline",
    ):
        prompt = _dynamic_outline_prompt(project, strategy)
        with st.spinner("Generating Dynamic Outline from current JSON strategy..."):
            result = run_codex(codex_template, prompt, project, ROOT, RUN_LOG_DIR)
        output_path = project / DYNAMIC_OUTLINE_FILENAME
        if result.returncode == 0 and output_path.is_file() and output_path.stat().st_size > 0:
            st.success(f"Generated {DYNAMIC_OUTLINE_FILENAME} from the current Dynamic JSON strategy.")
            st.rerun()
        elif result.returncode == 0:
            st.error(f"Generator finished but {DYNAMIC_OUTLINE_FILENAME} was not created.")
            st.code(result.output or "No generator output returned.", language=None)
        else:
            st.error(f"Dynamic Outline generator failed with exit code {result.returncode}.")
            st.code(result.output or "No generator output returned.", language=None)

    output_path = project / DYNAMIC_OUTLINE_FILENAME
    if output_path.is_file() and output_path.stat().st_size > 0:
        with st.expander("Current Dynamic Outline", expanded=False):
            try:
                st.markdown(output_path.read_text(encoding="utf-8"))
            except OSError as exc:
                st.error(f"Could not read Dynamic Outline: {exc}")

st.info(
    "Dynamic Outline generation is isolated to DW Flow and its Dynamic_ output. "
    "Writer, Final Script, old Workflow, old Outline, and Opus Writer logic are not connected or modified here."
)

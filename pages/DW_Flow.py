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
DYNAMIC_WRITER_PROMPT_FILENAME = "Dynamic_05_writer_prompt.md"
DYNAMIC_FINAL_SCRIPT_FILENAME = "Dynamic_06_final_script.md"
DYNAMIC_NARRATIVE_QA_FILENAME = "Dynamic_14_narrative_qa.md"

DYNAMIC_OUTPUTS = (
    ("Dynamic Outline", DYNAMIC_OUTLINE_FILENAME),
    ("Dynamic Writer Prompt", DYNAMIC_WRITER_PROMPT_FILENAME),
    ("Dynamic Final Script", DYNAMIC_FINAL_SCRIPT_FILENAME),
    ("Dynamic Narrative QA", DYNAMIC_NARRATIVE_QA_FILENAME),
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


def _dynamic_outline_prompt(project: Path) -> str:
    """Build one Windows-safe command-line argument; large strategy content stays on disk."""
    strategy_relative = DYNAMIC_STRATEGY_PATH.relative_to(ROOT).as_posix()
    project_relative = project.relative_to(ROOT).as_posix()
    return (
        "Act as the Dynamic Outline Generator for DW Flow. "
        f"Read the authoritative strategy JSON directly from {strategy_relative}. "
        f"Read relevant factual grounding files inside {project_relative}. "
        f"Create {project_relative}/{DYNAMIC_OUTLINE_FILENAME} and no other generated artifact. "
        "Interpret all JSON block names semantically at runtime with no built-in section meanings; follow enabled parent blocks and enabled children in saved order, follow their natural-language instructions, ignore disabled blocks, and apply enabled repeat mode/value/positions including ai_natural. "
        "Do not impose Hook, Main Body, Conclusion, CTA, Evidence, Story, or any hidden standard structure unless the current JSON requests it. "
        "JSON is authoritative for creative organization and project evidence is authoritative for factual content; never invent evidence to satisfy a block. "
        "Do not modify the strategy JSON or any old-pipeline file, and do not create or overwrite 05_script_outline.md, opus_writer_package.md, or 06_final_script.md. "
        f"Write only the finished writer-facing Markdown outline to {project_relative}/{DYNAMIC_OUTLINE_FILENAME} with no process commentary."
    )


def _dynamic_writer_prompt(project: Path) -> str:
    """Create the separate Dynamic writer prompt from the generated Dynamic outline."""
    project_relative = project.relative_to(ROOT).as_posix()
    strategy_relative = DYNAMIC_STRATEGY_PATH.relative_to(ROOT).as_posix()
    return (
        "Act as the Dynamic Writer Prompt Builder for the separate DW Flow. "
        f"Read the authoritative generated Dynamic outline from {project_relative}/{DYNAMIC_OUTLINE_FILENAME}. "
        f"Also read {strategy_relative} only to preserve the user's dynamic structural intent, and read relevant factual source, research, and medical files inside {project_relative} when needed to understand evidence boundaries. "
        f"Create {project_relative}/{DYNAMIC_WRITER_PROMPT_FILENAME} and no other generated artifact. "
        "Build a complete self-contained writer prompt that instructs the future script writer to turn the Dynamic outline into a natural, engaging, evidence-grounded narration. "
        "Treat the Dynamic outline as the authoritative creative plan for this run and preserve its semantic order, topic-specific reasoning, evidence limits, safety distinctions, and repeat or engagement intent. "
        "Do not impose any hidden standard script template, fixed Hook/Main Body/Conclusion headings, fixed section count, fixed hook formula, fixed CTA placement, or old Opus Writer structure unless the Dynamic outline itself requests it. "
        "Do not force the narration to say packaging-meta phrases such as the title promised, the thumbnail says, or similar references unless the Dynamic outline explicitly requires them. "
        "Do not invent facts, citations, statistics, medical claims, or source conclusions; project evidence remains factual authority. "
        "The prompt must tell the future writer to write narration rather than process commentary, to follow the outline intelligently rather than mechanically echoing outline bullets, and to preserve uncertainty and applicability limits. "
        "Keep this Dynamic path isolated: do not read instructions from or modify the old Opus Writer Prompt/template merely to construct this prompt; do not modify old Workflow, old Outline, old writer outputs, the Dynamic outline, or the strategy JSON. "
        f"Write only the finished reusable writer prompt to {project_relative}/{DYNAMIC_WRITER_PROMPT_FILENAME} with no commentary before or after it."
    )


def _dynamic_narrative_qa_prompt(project: Path) -> str:
    """Audit only the Dynamic script against Dynamic authorities, never the old blueprint."""
    project_relative = project.relative_to(ROOT).as_posix()
    strategy_relative = DYNAMIC_STRATEGY_PATH.relative_to(ROOT).as_posix()
    return (
        "Act as the Dynamic Narrative QA Agent for the separate DW Flow. "
        f"Audit {project_relative}/{DYNAMIC_FINAL_SCRIPT_FILENAME} against the authoritative Dynamic outline {project_relative}/{DYNAMIC_OUTLINE_FILENAME} and the Dynamic writer instructions {project_relative}/{DYNAMIC_WRITER_PROMPT_FILENAME}. "
        f"Use {strategy_relative} only as supporting evidence of the user's intended dynamic block order, enabled state, and repeat placement. "
        f"Write the finished QA report only to {project_relative}/{DYNAMIC_NARRATIVE_QA_FILENAME}. "
        "This QA must judge the script that exists: narrative progression, hook effectiveness and payoff timing, retention, repetition, transition quality, emotional balance, viewer trust, natural spoken flow, engagement placement, conclusion strength, and whether the Dynamic outline's semantic plan was actually delivered. "
        "For repetition, distinguish necessary safety reminders from redundant reteaching and identify only repetition with no meaningful new decision, evidence, mechanism, consequence, or action. "
        "Check persona drift and flag any doctor, clinician, patient-care, diagnosis, prescribing, or personal-clinical-experience voice when the intended presenter is a health educator. "
        "Estimate narration word count and runtime using the configured WPM from config.json; report runtime as advisory against the configured preferred range, not as a narrative failure by itself. If a hook can be shortened, do not recommend simply deleting useful value when that would unnecessarily reduce the intended total runtime; recommend redistribution into the appropriate later Dynamic section when useful. "
        "Factual or medical concerns may be marked for later medical review, but Narrative QA must not invent medical corrections or fail the narrative solely because a source needs verification. "
        "CRITICAL AUTHORITY RULE: never read, compare against, cite, enforce, or use 05_script_outline.md, the old Narrative QA output, old Opus Writer Prompt, old workflow gates, or any old blueprint as an authority. Never reorder Dynamic sections because an old outline differs. Never require an old checklist, CTA position, heading scheme, channel wording, or structure unless the Dynamic outline itself requires it. "
        "Do not impose Hook/Main Content/Conclusion headings or any standard section template unless present in the Dynamic authority files. "
        "Produce a useful Markdown QA report with an overall verdict, scorecard, concise executive summary, semantic progression/repetition findings, Dynamic-outline fidelity audit, persona/tone audit, runtime advisory, issue list ranked by severity, and precise revision patches only for genuine Dynamic narrative defects. Each revision reason must state the narrative defect itself rather than old-pipeline compliance. "
        "PASS is allowed when there are no material narrative defects; PASS WITH REVISIONS is appropriate when useful corrections are needed. Do not modify the script, outline, writer prompt, strategy JSON, or any old-pipeline file. "
        f"Create only {project_relative}/{DYNAMIC_NARRATIVE_QA_FILENAME} and no other generated artifact, with no process commentary outside the report."
    )


def _repeat_summary(repeat: dict) -> str:
    mode = str(repeat.get("mode") or "seconds")
    if mode == "specific_positions":
        detail = str(repeat.get("positions") or "").strip() or "positions not specified"
    elif mode == "ai_natural":
        detail = "AI decides naturally"
    else:
        detail = str(repeat.get("value") or "").strip() or "value not specified"
    return f"Repeat: {mode} · {detail}"


st.set_page_config(page_title="DW Flow", page_icon="🧩", layout="wide")
st.title("DW Flow")
st.caption(
    "Separate Dynamic workflow. The existing Workflow, Outline, Opus Writer Prompt, Narrative QA, and old outputs are not used or modified by this page."
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
        elif path.is_file() and path.stat().st_size > 0:
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
                    st.caption(_repeat_summary(repeat))
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
                            st.caption(_repeat_summary(child_repeat))
                else:
                    st.caption("No enabled child blocks.")

    st.markdown("### Generate Dynamic Outline")
    st.caption(
        "The generator reads the current JSON file directly at run time. Creative block names and section structure are not hardcoded in DW Flow."
    )
    config = _load_config()
    codex_template = detect_codex_template(config)
    can_generate = bool(structure) and bool(codex_template)
    if not codex_template:
        st.warning("Direct Codex command is not configured/available, so Dynamic generation cannot run yet.")
    if st.button(
        "Generate Dynamic Outline",
        type="primary",
        disabled=not can_generate,
        key="dw_generate_dynamic_outline",
    ):
        prompt = _dynamic_outline_prompt(project)
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

    outline_path = project / DYNAMIC_OUTLINE_FILENAME
    if outline_path.is_file() and outline_path.stat().st_size > 0:
        with st.expander("Current Dynamic Outline", expanded=False):
            try:
                st.markdown(outline_path.read_text(encoding="utf-8"))
            except OSError as exc:
                st.error(f"Could not read Dynamic Outline: {exc}")

        st.markdown("### Generate Dynamic Writer Prompt")
        st.caption(
            "Builds a separate writer prompt from the current Dynamic Outline. It does not use or modify the old Opus Writer Prompt."
        )
        if st.button(
            "Generate Dynamic Writer Prompt",
            type="primary",
            disabled=not bool(codex_template),
            key="dw_generate_dynamic_writer_prompt",
        ):
            prompt = _dynamic_writer_prompt(project)
            with st.spinner("Generating Dynamic Writer Prompt from the current Dynamic Outline..."):
                result = run_codex(codex_template, prompt, project, ROOT, RUN_LOG_DIR)
            writer_prompt_path = project / DYNAMIC_WRITER_PROMPT_FILENAME
            if result.returncode == 0 and writer_prompt_path.is_file() and writer_prompt_path.stat().st_size > 0:
                st.success(f"Generated {DYNAMIC_WRITER_PROMPT_FILENAME} from the current Dynamic Outline.")
                st.rerun()
            elif result.returncode == 0:
                st.error(f"Generator finished but {DYNAMIC_WRITER_PROMPT_FILENAME} was not created.")
                st.code(result.output or "No generator output returned.", language=None)
            else:
                st.error(f"Dynamic Writer Prompt generator failed with exit code {result.returncode}.")
                st.code(result.output or "No generator output returned.", language=None)

    writer_prompt_path = project / DYNAMIC_WRITER_PROMPT_FILENAME
    if writer_prompt_path.is_file() and writer_prompt_path.stat().st_size > 0:
        with st.expander("Current Dynamic Writer Prompt", expanded=False):
            try:
                st.markdown(writer_prompt_path.read_text(encoding="utf-8"))
            except OSError as exc:
                st.error(f"Could not read Dynamic Writer Prompt: {exc}")

    final_script_path = project / DYNAMIC_FINAL_SCRIPT_FILENAME
    if final_script_path.is_file() and final_script_path.stat().st_size > 0:
        with st.expander("Current Dynamic Final Script", expanded=False):
            try:
                st.markdown(final_script_path.read_text(encoding="utf-8"))
            except OSError as exc:
                st.error(f"Could not read Dynamic Final Script: {exc}")

        st.markdown("### Run Dynamic Narrative QA")
        st.caption(
            "Audits the Dynamic Final Script only against Dynamic authorities. The old Narrative QA and old 05_script_outline.md are not used."
        )
        if st.button(
            "Run Dynamic Narrative QA",
            type="primary",
            disabled=not bool(codex_template),
            key="dw_run_dynamic_narrative_qa",
        ):
            prompt = _dynamic_narrative_qa_prompt(project)
            with st.spinner("Running isolated Dynamic Narrative QA..."):
                result = run_codex(codex_template, prompt, project, ROOT, RUN_LOG_DIR)
            qa_path = project / DYNAMIC_NARRATIVE_QA_FILENAME
            if result.returncode == 0 and qa_path.is_file() and qa_path.stat().st_size > 0:
                st.success(f"Generated {DYNAMIC_NARRATIVE_QA_FILENAME} from Dynamic authorities only.")
                st.rerun()
            elif result.returncode == 0:
                st.error(f"QA finished but {DYNAMIC_NARRATIVE_QA_FILENAME} was not created.")
                st.code(result.output or "No QA output returned.", language=None)
            else:
                st.error(f"Dynamic Narrative QA failed with exit code {result.returncode}.")
                st.code(result.output or "No QA output returned.", language=None)

    qa_path = project / DYNAMIC_NARRATIVE_QA_FILENAME
    if qa_path.is_file() and qa_path.stat().st_size > 0:
        with st.expander("Current Dynamic Narrative QA", expanded=False):
            try:
                st.markdown(qa_path.read_text(encoding="utf-8"))
            except OSError as exc:
                st.error(f"Could not read Dynamic Narrative QA: {exc}")

st.info(
    "Dynamic Outline, Dynamic Writer Prompt, and Dynamic Narrative QA are isolated to DW Flow and Dynamic_ outputs. "
    "Old Workflow, old Outline, old Opus Writer, and old Narrative QA logic are not connected or modified here."
)

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
DYNAMIC_STRATEGY_VALIDATION_FILENAME = "Dynamic_05_strategy_validation.md"
DYNAMIC_WRITER_PROMPT_FILENAME = "Dynamic_05_writer_prompt.md"
DYNAMIC_FINAL_SCRIPT_FILENAME = "Dynamic_06_final_script.md"
DYNAMIC_NARRATIVE_QA_FILENAME = "Dynamic_14_narrative_qa.md"
DYNAMIC_MEDICAL_GATE_2_FILENAME = "Dynamic_15_medical_gate_2.md"

DYNAMIC_OUTPUTS = (
    ("Dynamic Outline", DYNAMIC_OUTLINE_FILENAME),
    ("Dynamic Strategy Validation", DYNAMIC_STRATEGY_VALIDATION_FILENAME),
    ("Dynamic Writer Prompt", DYNAMIC_WRITER_PROMPT_FILENAME),
    ("Dynamic Final Script", DYNAMIC_FINAL_SCRIPT_FILENAME),
    ("Dynamic Narrative QA", DYNAMIC_NARRATIVE_QA_FILENAME),
    ("Dynamic Medical Gate 2", DYNAMIC_MEDICAL_GATE_2_FILENAME),
)


def _project_names() -> list[str]:
    if not PROJECTS_DIR.is_dir():
        return []
    return sorted([p.name for p in PROJECTS_DIR.iterdir() if p.is_dir()], key=str.casefold)


def _load_strategy() -> tuple[dict | None, str]:
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
    structure: list[dict] = []
    for parent in payload.get("blocks", []):
        if not isinstance(parent, dict) or not parent.get("enabled", True):
            continue
        children = [c for c in parent.get("children", []) if isinstance(c, dict) and c.get("enabled", True)]
        structure.append({"parent": parent, "children": children})
    return structure


def _load_config() -> dict:
    try:
        payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _dynamic_outline_prompt(project: Path) -> str:
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


def _dynamic_strategy_validation_prompt(project: Path) -> str:
    strategy_relative = DYNAMIC_STRATEGY_PATH.relative_to(ROOT).as_posix()
    project_relative = project.relative_to(ROOT).as_posix()
    return (
        "Act as the Dynamic Strategy Validation Gate for the separate DW Flow. "
        f"Treat {strategy_relative} as the sole authority for creative strategy and audit {project_relative}/{DYNAMIC_OUTLINE_FILENAME} against it. "
        f"Write the finished validation report only to {project_relative}/{DYNAMIC_STRATEGY_VALIDATION_FILENAME}. "
        "Validate every parent and child block, including enabled and disabled state, saved parent order, saved child order, natural-language instruction intent, and every enabled repeat rule. "
        "For enabled blocks, verify the outline contains a semantically faithful implementation rather than merely matching a label. For disabled blocks, verify their unique instructed material was not injected as a required strategy element. "
        "For repeat modes seconds, minutes, blocks, specific_positions, and ai_natural, judge whether the outline faithfully expresses the requested recurrence or placement at the level the outline can reasonably specify. Do not invent exact timing evidence when the outline does not contain timing. Mark genuinely unverifiable repeat details as WARNING rather than pretending they passed. "
        "Check that the outline did not silently omit, materially weaken, contradict, reorder, or replace a JSON instruction, and that it did not inject a hidden fixed Hook/Main Body/Conclusion, CTA, evidence, story, or other standard structure not requested by the active JSON. "
        "Do not judge medical truth, research quality, prose quality, retention quality, or final-script execution in this gate. This gate answers only whether JSON strategy was faithfully translated into the Dynamic Outline. "
        "CRITICAL ISOLATION RULE: never read, compare against, cite, enforce, or use 05_script_outline.md, old Outline logic, old Opus Writer Prompt, old Narrative QA, old Medical Gate 2, old workflow gates, or any old blueprint as authority. "
        "Verdict semantics are strict: PASS only when all enabled strategy requirements are faithfully represented, disabled strategy is excluded, order is correct, and no material JSON instruction is missing or contradicted. PASS WITH WARNINGS only when there is no known strategy violation but one or more instructions or repeat placements are genuinely ambiguous or unverifiable from the outline. FAIL when any enabled parent/child is missing, materially misinterpreted, out of required order, any disabled strategy is materially injected, any required repeat/placement is violated, or hidden structure overrides the JSON. "
        "Produce concise Markdown with overall verdict, parent-by-parent audit, child-by-child audit, order audit, disabled-block audit, repeat/placement audit, hidden-structure audit, issues ranked by severity, and exact correction instructions for the Dynamic Outline generator when needed. Do not rewrite the outline yourself. "
        "Do not modify the JSON, Dynamic Outline, or any old-pipeline file. "
        f"Create only {project_relative}/{DYNAMIC_STRATEGY_VALIDATION_FILENAME} and no other generated artifact, with no process commentary outside the report."
    )


def _dynamic_writer_prompt(project: Path) -> str:
    project_relative = project.relative_to(ROOT).as_posix()
    strategy_relative = DYNAMIC_STRATEGY_PATH.relative_to(ROOT).as_posix()
    return (
        "Act as the Dynamic Writer Prompt Builder for the separate DW Flow. "
        f"Read the authoritative generated Dynamic outline from {project_relative}/{DYNAMIC_OUTLINE_FILENAME}. "
        f"Also read {strategy_relative} only to preserve the user's dynamic structural intent, and read relevant factual source, research, and medical files inside {project_relative} when needed to understand evidence boundaries. "
        f"Create {project_relative}/{DYNAMIC_WRITER_PROMPT_FILENAME} and no other generated artifact. "
        "Build a complete self-contained writer prompt that instructs the future script writer to turn the Dynamic outline into natural, engaging, evidence-grounded narration. "
        "Treat the Dynamic outline as the authoritative creative plan and preserve its semantic order, reasoning, evidence limits, safety distinctions, and repeat or engagement intent. "
        "Do not impose a hidden standard template, fixed Hook/Main Body/Conclusion headings, fixed section count, hook formula, CTA placement, or old Opus Writer structure unless the Dynamic outline requests it. "
        "Do not force packaging-meta phrases such as the title promised or the thumbnail says unless explicitly required. Do not invent facts, citations, statistics, medical claims, or source conclusions. "
        "Tell the future writer to write narration rather than process commentary, follow the outline intelligently rather than mechanically echoing bullets, and preserve uncertainty and applicability limits. "
        "Keep this Dynamic path isolated: do not read instructions from or modify the old Opus Writer Prompt/template merely to construct this prompt; do not modify old Workflow, old Outline, old writer outputs, the Dynamic outline, or strategy JSON. "
        f"Write only the finished reusable writer prompt to {project_relative}/{DYNAMIC_WRITER_PROMPT_FILENAME} with no commentary before or after it."
    )


def _dynamic_narrative_qa_prompt(project: Path) -> str:
    project_relative = project.relative_to(ROOT).as_posix()
    strategy_relative = DYNAMIC_STRATEGY_PATH.relative_to(ROOT).as_posix()
    return (
        "Act as the Dynamic Narrative QA Agent for the separate DW Flow. "
        f"Audit {project_relative}/{DYNAMIC_FINAL_SCRIPT_FILENAME} against {project_relative}/{DYNAMIC_OUTLINE_FILENAME} and {project_relative}/{DYNAMIC_WRITER_PROMPT_FILENAME}. "
        f"Use {strategy_relative} only as supporting evidence of intended dynamic block order, enabled state, and repeat placement. "
        f"Write the finished QA report only to {project_relative}/{DYNAMIC_NARRATIVE_QA_FILENAME}. "
        "Judge narrative progression, hook effectiveness and payoff timing, retention, repetition, transitions, emotional balance, viewer trust, natural spoken flow, engagement placement, conclusion strength, and Dynamic semantic delivery. "
        "Distinguish necessary safety reminders from redundant reteaching. Check persona drift and flag doctor, clinician, patient-care, diagnosis, prescribing, or personal-clinical-experience voice when the presenter is a health educator. "
        "Estimate word count and runtime using configured WPM; runtime is advisory against the configured preferred range. If a hook can be shortened, do not simply delete useful value when redistribution later would preserve useful runtime. "
        "Factual or medical concerns may be marked for later medical review, but Narrative QA must not invent medical corrections or fail solely because a source needs verification. "
        "CRITICAL AUTHORITY RULE: never read, compare against, cite, enforce, or use 05_script_outline.md, old Narrative QA, old Opus Writer Prompt, old workflow gates, or any old blueprint as authority. Never reorder Dynamic sections because an old outline differs or require an old checklist, CTA position, heading scheme, channel wording, or structure. "
        "Do not impose Hook/Main Content/Conclusion headings unless present in Dynamic authority files. "
        "Produce Markdown with verdict, scorecard, executive summary, semantic progression/repetition findings, Dynamic-outline fidelity audit, persona/tone audit, runtime advisory, issues ranked by severity, and precise revision patches only for genuine Dynamic narrative defects. "
        "PASS is allowed when there are no material narrative defects. Do not modify any source file. "
        f"Create only {project_relative}/{DYNAMIC_NARRATIVE_QA_FILENAME} and no other generated artifact."
    )


def _dynamic_medical_gate_2_prompt(project: Path) -> str:
    project_relative = project.relative_to(ROOT).as_posix()
    return (
        "Act as Dynamic Medical Gate 2 for the separate DW Flow. "
        f"Review the actual narration in {project_relative}/{DYNAMIC_FINAL_SCRIPT_FILENAME}. "
        f"Read {project_relative}/{DYNAMIC_NARRATIVE_QA_FILENAME} only for context about narrative handoff, never as medical evidence. "
        f"Use the project's factual evidence files inside {project_relative} as the medical authority, prioritizing source-grounded research and claim records such as 02_research_claims.json, 02_research_sheet.md, 02_external_deep_research.md, 13_fact_check_log.md, and 13_gate1_disposition.json when they exist. Read other project evidence files when needed to trace a claim. "
        f"Write the finished gate report only to {project_relative}/{DYNAMIC_MEDICAL_GATE_2_FILENAME}. "
        "Audit every material medical or health claim in the final narration for source support, faithful wording, population and age applicability, screening-versus-diagnostic context, eligibility and stopping criteria, contraindications or exceptions, numerical accuracy, guideline attribution, uncertainty, evidence strength, causal overstatement, benefit/harm framing, and whether a population-level finding is improperly personalized. "
        "For each material claim classify it as SUPPORTED, SUPPORTED WITH LIMITS, NEEDS REVISION, or UNSUPPORTED. Trace supported claims to the actual project evidence identifier/file where possible. Never treat the Dynamic outline, Dynamic writer prompt, Narrative QA, title, thumbnail, or packaging language as factual authority. "
        "Do not use general model memory to silently fill evidence gaps. If the project evidence does not support a claim, say so and require narrowing, removal, or source verification rather than inventing support. Do not add new medical claims merely to improve the script. "
        "Preserve the health-educator boundary: flag language that becomes individualized diagnosis, treatment, prescribing, guaranteed outcome, clinician impersonation, or unsafe advice. Also check that safety caveats are proportionate and that routine-screening guidance is not applied to symptoms, abnormal-result follow-up, surveillance, or other clinically different pathways. "
        "CRITICAL ISOLATION RULE: do not read, cite, enforce, modify, or use old Medical Gate 2 outputs, old 05_script_outline.md, old Narrative QA, old Opus Writer Prompt, or old workflow gates as authority. The final Dynamic script is the claim surface; project research/evidence is factual authority. "
        "Return PASS only when no material medical claim requires correction. Return PASS WITH REVISIONS when bounded wording fixes can resolve issues, and FAIL when a material claim is unsupported, materially misleading, unsafe, or cannot be repaired without new evidence. "
        "Produce a concise Markdown report containing overall verdict, medical safety summary, claim audit table with script claim/assessment/evidence trace/reason, population-and-applicability audit, guideline-and-number audit, educator-boundary audit, unresolved evidence flags, and exact minimal revision patches for claims that need changes. Do not rewrite sound narrative for style. "
        "Do not modify the Dynamic script, research, outline, writer prompt, Narrative QA, strategy JSON, or any old-pipeline file. "
        f"Create only {project_relative}/{DYNAMIC_MEDICAL_GATE_2_FILENAME} and no other generated artifact, with no process commentary outside the report."
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


def _show_markdown(path: Path, label: str) -> None:
    if not path.is_file() or path.stat().st_size <= 0:
        return
    with st.expander(label, expanded=False):
        try:
            st.markdown(path.read_text(encoding="utf-8"))
        except OSError as exc:
            st.error(f"Could not read {path.name}: {exc}")


def _run_generation(button_label: str, key: str, spinner: str, prompt: str, output_path: Path, success: str, codex_template: str) -> None:
    if st.button(button_label, type="primary", disabled=not bool(codex_template), key=key):
        with st.spinner(spinner):
            result = run_codex(codex_template, prompt, project, ROOT, RUN_LOG_DIR)
        if result.returncode == 0 and output_path.is_file() and output_path.stat().st_size > 0:
            st.success(success)
            st.rerun()
        elif result.returncode == 0:
            st.error(f"Generator finished but {output_path.name} was not created.")
            st.code(result.output or "No generator output returned.", language=None)
        else:
            st.error(f"Generator failed with exit code {result.returncode}.")
            st.code(result.output or "No generator output returned.", language=None)


st.set_page_config(page_title="DW Flow", page_icon="🧩", layout="wide")
st.title("DW Flow")
st.caption("Separate Dynamic workflow. Existing old Workflow, Outline, Opus Writer, Narrative QA, Medical Gate 2, and old outputs are not used or modified by this page.")

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
config = _load_config()
codex_template = detect_codex_template(config)

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
    st.caption("Exact enabled parent/child order currently supplied by Outline Builder JSON. Disabled blocks stay saved but are not active.")
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
                for child_number, child in enumerate(item["children"], 1):
                    child_name = str(child.get("name") or f"Child {child_number}").strip()
                    st.markdown(f"**{number}.{child_number} {child_name}**")
                    child_instruction = str(child.get("instruction") or "").strip()
                    if child_instruction:
                        st.write(child_instruction)
                    child_repeat = child.get("repeat") if isinstance(child.get("repeat"), dict) else {}
                    if child_repeat.get("enabled"):
                        st.caption(_repeat_summary(child_repeat))

    if not codex_template:
        st.warning("Direct Codex command is not configured/available, so Dynamic generation cannot run yet.")

    st.markdown("### Generate Dynamic Outline")
    st.caption("Reads the current JSON directly at run time; creative block names and section structure are not hardcoded.")
    outline_path = project / DYNAMIC_OUTLINE_FILENAME
    _run_generation("Generate Dynamic Outline", "dw_generate_dynamic_outline", "Generating Dynamic Outline from current JSON strategy...", _dynamic_outline_prompt(project), outline_path, f"Generated {DYNAMIC_OUTLINE_FILENAME} from the current Dynamic JSON strategy.", codex_template if structure else "")
    _show_markdown(outline_path, "Current Dynamic Outline")

    strategy_validation_path = project / DYNAMIC_STRATEGY_VALIDATION_FILENAME
    if outline_path.is_file() and outline_path.stat().st_size > 0:
        st.markdown("### Validate Dynamic Strategy")
        st.caption("Dedicated JSON → Outline gate. Checks enabled/disabled blocks, parent/child order, instruction intent, repeat placement, and hidden-structure injection before writing begins.")
        _run_generation("Validate Dynamic Strategy", "dw_validate_dynamic_strategy", "Validating Dynamic Outline against the current JSON strategy...", _dynamic_strategy_validation_prompt(project), strategy_validation_path, f"Generated {DYNAMIC_STRATEGY_VALIDATION_FILENAME} from JSON → Outline validation.", codex_template)
    _show_markdown(strategy_validation_path, "Current Dynamic Strategy Validation")

    writer_prompt_path = project / DYNAMIC_WRITER_PROMPT_FILENAME
    if outline_path.is_file() and outline_path.stat().st_size > 0:
        st.markdown("### Generate Dynamic Writer Prompt")
        st.caption("Builds a separate writer prompt from the current Dynamic Outline. It does not use or modify the old Opus Writer Prompt.")
        _run_generation("Generate Dynamic Writer Prompt", "dw_generate_dynamic_writer_prompt", "Generating Dynamic Writer Prompt from the current Dynamic Outline...", _dynamic_writer_prompt(project), writer_prompt_path, f"Generated {DYNAMIC_WRITER_PROMPT_FILENAME} from the current Dynamic Outline.", codex_template)
    _show_markdown(writer_prompt_path, "Current Dynamic Writer Prompt")

    final_script_path = project / DYNAMIC_FINAL_SCRIPT_FILENAME
    _show_markdown(final_script_path, "Current Dynamic Final Script")

    qa_path = project / DYNAMIC_NARRATIVE_QA_FILENAME
    if final_script_path.is_file() and final_script_path.stat().st_size > 0:
        st.markdown("### Run Dynamic Narrative QA")
        st.caption("Audits the Dynamic Final Script only against Dynamic authorities. Old Narrative QA and old 05_script_outline.md are not used.")
        _run_generation("Run Dynamic Narrative QA", "dw_run_dynamic_narrative_qa", "Running isolated Dynamic Narrative QA...", _dynamic_narrative_qa_prompt(project), qa_path, f"Generated {DYNAMIC_NARRATIVE_QA_FILENAME} from Dynamic authorities only.", codex_template)
    _show_markdown(qa_path, "Current Dynamic Narrative QA")

    mg2_path = project / DYNAMIC_MEDICAL_GATE_2_FILENAME
    if final_script_path.is_file() and final_script_path.stat().st_size > 0 and qa_path.is_file() and qa_path.stat().st_size > 0:
        st.markdown("### Run Dynamic Medical Gate 2")
        st.caption("Checks the Dynamic Final Script against project research/evidence. Dynamic Narrative QA is context only; old Medical Gate 2 and old pipeline authorities are not used.")
        _run_generation("Run Dynamic Medical Gate 2", "dw_run_dynamic_medical_gate_2", "Running isolated Dynamic Medical Gate 2...", _dynamic_medical_gate_2_prompt(project), mg2_path, f"Generated {DYNAMIC_MEDICAL_GATE_2_FILENAME} from project evidence and the Dynamic Final Script.", codex_template)
    _show_markdown(mg2_path, "Current Dynamic Medical Gate 2")

st.info("Dynamic Outline, Strategy Validation, Writer Prompt, Narrative QA, and Medical Gate 2 are isolated to DW Flow and Dynamic_ outputs. Old Workflow, Outline, Opus Writer, Narrative QA, and Medical Gate 2 logic are not connected or modified here.")

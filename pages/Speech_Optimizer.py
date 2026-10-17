from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from v31_core import detect_codex_template, run_codex

ROOT = Path(__file__).resolve().parents[1]
PROJECTS_DIR = ROOT / "Projects"
CONFIG_PATH = ROOT / "config.json"
RUN_LOG_DIR = ROOT / "RunLogs"
FINAL_SCRIPT_FILENAME = "06_final_script.md"
VOICE_SCRIPT_FILENAME = "06a_voice_script.md"
VOICE_CHECKLIST_FILENAME = "06b_voice_checklist.md"


def _project_names() -> list[str]:
    if not PROJECTS_DIR.is_dir():
        return []
    return sorted([p.name for p in PROJECTS_DIR.iterdir() if p.is_dir()], key=str.casefold)


def _load_config() -> dict:
    try:
        payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _speech_optimizer_prompt(project: Path) -> str:
    project_relative = project.relative_to(ROOT).as_posix()
    return (
        "Act as the Production Speech Optimizer. "
        f"Use {project_relative}/{FINAL_SCRIPT_FILENAME} as the sole canonical narration input. "
        "The script is already final and approved before it reaches you. Do not require, read, validate, or depend on any outline, writer prompt, strategy validation, Narrative QA, Medical Gate, research gate, host-identity gate, or other upstream workflow artifact. "
        f"Create exactly two Production-compatible handoff files: {project_relative}/{VOICE_SCRIPT_FILENAME} and {project_relative}/{VOICE_CHECKLIST_FILENAME}. "
        f"In {VOICE_SCRIPT_FILENAME}, preserve every meaning, qualifier, negation, number, age, guideline attribution, safety distinction, CTA meaning, and approved wording from {FINAL_SCRIPT_FILENAME}. "
        "Do not add, remove, reorder, summarize, fact-check, strengthen, soften, medically revise, or creatively rewrite the script. "
        "Perform delivery-only optimization for natural TTS/voice synthesis: remove non-spoken Markdown organizational headings and other non-spoken formatting, normalize smart quotes/dashes/ellipses/decorative Unicode conservatively, normalize repeated punctuation, use simple sentence punctuation where safe, expand only ordinary contractions when needed for synthesis clarity, and retain simple ASCII punctuation plus necessary intra-word hyphens for natural pacing and pronunciation. "
        "Attach pronunciation guidance only when needed and without changing spoken wording or meaning. Never alter a technical term merely to make pronunciation easier. "
        f"In {VOICE_CHECKLIST_FILENAME}, document Speech QA, paragraph statistics, pronunciation review, chapter plan, and upload checklist. State that the sole source was {FINAL_SCRIPT_FILENAME}. Do not claim or require any upstream gate verdict. "
        f"Do not modify {project_relative}/{FINAL_SCRIPT_FILENAME} or any other project artifact. "
        f"Write only {project_relative}/{VOICE_SCRIPT_FILENAME} and {project_relative}/{VOICE_CHECKLIST_FILENAME}; create no other artifact and no process commentary."
    )


st.set_page_config(page_title="Speech Optimizer", page_icon="🎙️", layout="wide")
st.title("Speech Optimizer")
st.caption("Production-only speech handoff. Any non-empty 06_final_script.md is accepted; no upstream QA, medical gate, outline, writer, or strategy approval is required.")

projects = _project_names()
if not projects:
    st.info("No project folders are available yet.")
    st.stop()

project_name = st.selectbox("Project", projects, key="speech_optimizer_project")
project = PROJECTS_DIR / project_name
final_script_path = project / FINAL_SCRIPT_FILENAME
voice_script_path = project / VOICE_SCRIPT_FILENAME
voice_checklist_path = project / VOICE_CHECKLIST_FILENAME

config = _load_config()
codex_template = detect_codex_template(config)

if final_script_path.is_file() and final_script_path.stat().st_size > 0:
    st.success(f"READY · {FINAL_SCRIPT_FILENAME} found. Speech Optimizer is unlocked.")
    with st.expander("Current Final Script", expanded=False):
        try:
            st.markdown(final_script_path.read_text(encoding="utf-8"))
        except OSError as exc:
            st.error(f"Could not read {FINAL_SCRIPT_FILENAME}: {exc}")
else:
    st.warning(f"{FINAL_SCRIPT_FILENAME} is missing or empty. Add any final script with this exact filename to the selected project.")

if not codex_template:
    st.warning("Direct Codex command is not configured/available, so Speech Optimizer cannot run yet.")

speech_ready = final_script_path.is_file() and final_script_path.stat().st_size > 0
if st.button("Run Speech Optimizer", type="primary", disabled=not (speech_ready and bool(codex_template)), key="run_independent_speech_optimizer"):
    with st.spinner("Optimizing final narration for speech and creating Production handoff files..."):
        result = run_codex(codex_template, _speech_optimizer_prompt(project), project, ROOT, RUN_LOG_DIR)
    outputs_ready = (
        voice_script_path.is_file() and voice_script_path.stat().st_size > 0
        and voice_checklist_path.is_file() and voice_checklist_path.stat().st_size > 0
    )
    if result.returncode == 0 and outputs_ready:
        st.success(f"Created {VOICE_SCRIPT_FILENAME} and {VOICE_CHECKLIST_FILENAME}. Production handoff is ready.")
        st.rerun()
    elif result.returncode == 0:
        st.error(f"Speech Optimizer finished but both {VOICE_SCRIPT_FILENAME} and {VOICE_CHECKLIST_FILENAME} were not created.")
        st.code(result.output or "No generator output returned.", language=None)
    else:
        st.error(f"Speech Optimizer failed with exit code {result.returncode}.")
        st.code(result.output or "No generator output returned.", language=None)

for path, label in (
    (voice_script_path, "Current Production Voice Script"),
    (voice_checklist_path, "Current Production Voice Checklist"),
):
    if path.is_file() and path.stat().st_size > 0:
        with st.expander(label, expanded=False):
            try:
                st.markdown(path.read_text(encoding="utf-8"))
            except OSError as exc:
                st.error(f"Could not read {path.name}: {exc}")

st.info("Flow: 06_final_script.md → Speech Optimizer → 06a_voice_script.md + 06b_voice_checklist.md → existing Production pipeline.")

from __future__ import annotations

import json
import re
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
VOICE_SCRIPT_FILENAME = "06a_voice_script.md"
VOICE_CHECKLIST_FILENAME = "06b_voice_checklist.md"

DYNAMIC_OUTPUTS = (
    ("Dynamic Outline", DYNAMIC_OUTLINE_FILENAME),
    ("Dynamic Strategy Validation", DYNAMIC_STRATEGY_VALIDATION_FILENAME),
    ("Dynamic Writer Prompt", DYNAMIC_WRITER_PROMPT_FILENAME),
    ("Dynamic Final Script", DYNAMIC_FINAL_SCRIPT_FILENAME),
    ("Dynamic Narrative QA", DYNAMIC_NARRATIVE_QA_FILENAME),
    ("Dynamic Medical Gate 2", DYNAMIC_MEDICAL_GATE_2_FILENAME),
    ("Production Voice Script", VOICE_SCRIPT_FILENAME),
    ("Production Voice Checklist", VOICE_CHECKLIST_FILENAME),
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
        "RANKING AUTHORITY RULE: Explicit instructions in the current strategy JSON for ranking, a countdown, list order, or a ranking criterion are the highest creative-strategy authority and must be preserved. The LIST PROGRESSION RULE below is only a default when the current JSON leaves all of those matters unspecified. Project evidence remains the factual authority: never invent an evidence hierarchy, medical superlative, or unsupported factual ranking to satisfy JSON. If an explicit JSON factual ranking criterion cannot be supported by project evidence, preserve that strategy-versus-evidence conflict visibly in the outline rather than silently converting the requested ranked structure to an unranked progression. "
        "LIST PROGRESSION RULE (DEFAULT ONLY WHEN JSON LEAVES RANKING/COUNTDOWN/LIST ORDER/RANKING CRITERION UNSPECIFIED): When the topic contains a genuinely rankable list and the project evidence supports a strongest or highest-value item, prefer a reverse countdown from the lowest rank toward #1. Choose one explicit evidence-supported ranking criterion, such as strength of evidence, size of benefit, or practical value; state that criterion in the opening/hook and apply it consistently. Make #1 the strongest evidence-supported payoff and tease it early as an open loop. The opening list item must still be engaging and relatable, not filler or deliberately weak. In health topics never rank by fear, danger, deadliness, shock, or similar alarm framing. If the items are not genuinely rankable, do not fabricate a ranking, do not call any item #1 most important, and do not imply an evidence hierarchy that the sources do not support. Instead choose the order with the strongest natural narrative progression; a surprising or especially useful item may be placed last as a retention payoff without claiming that it ranks highest. "
        "If presenter identification is requested, describe the channel or purpose neutrally; never make the AI presenter claim to be a human health educator, clinician, doctor, or credentialed professional, and never invent first-person qualifications or clinical experience. " 
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
        "RANKING PRECEDENCE: Treat every explicit JSON instruction for ranking, a countdown, list order, or a ranking criterion as the requested creative structure. The generic LIST PROGRESSION RULE is a default only when the JSON leaves those matters unspecified; do not fail, weaken, or require removal of an explicitly requested ranked countdown merely because a generic progression would prefer an unranked list. Project evidence remains factual authority: do not treat an unsupported factual ranking as validated evidence, but require the outline to preserve the explicit strategy-versus-evidence conflict visibly rather than silently converting the JSON structure to unranked. "
        "Check that the outline did not silently omit, materially weaken, contradict, reorder, or replace a JSON instruction, and that it did not inject a hidden fixed Hook/Main Body/Conclusion, CTA, evidence, story, or other standard structure not requested by the active JSON. "
        "Do not judge medical truth, research quality, prose quality, retention quality, or final-script execution in this gate. This gate answers only whether JSON strategy was faithfully translated into the Dynamic Outline. "
        "CRITICAL ISOLATION RULE: never read, compare against, cite, enforce, or use 05_script_outline.md, old Outline logic, old Opus Writer Prompt, old Narrative QA, old Medical Gate 2, old workflow gates, or any old blueprint as authority. "
        "Verdict semantics are strict: PASS only when all enabled strategy requirements are faithfully represented, disabled strategy is excluded, order is correct, and no material JSON instruction is missing or contradicted. PASS WITH WARNINGS only when there is no known strategy violation but one or more instructions or repeat placements are genuinely ambiguous or unverifiable from the outline. FAIL when any enabled parent/child is missing, materially misinterpreted, out of required order, any disabled strategy is materially injected, any required repeat/placement is violated, or hidden structure overrides the JSON. "
        "Produce concise Markdown with overall verdict, parent-by-parent audit, child-by-child audit, order audit, disabled-block audit, repeat/placement audit, hidden-structure audit, issues ranked by severity, and exact correction instructions for the Dynamic Outline generator when needed. Do not rewrite the outline yourself. "
        "Do not modify the JSON, Dynamic Outline, or any old-pipeline file. "
        f"Create only {project_relative}/{DYNAMIC_STRATEGY_VALIDATION_FILENAME} and no other generated artifact, with no process commentary outside the report."
    )


def _dynamic_outline_fix_prompt(project: Path) -> str:
    strategy_relative = DYNAMIC_STRATEGY_PATH.relative_to(ROOT).as_posix()
    project_relative = project.relative_to(ROOT).as_posix()
    return (
        "Act as the Dynamic Outline Revision Agent for the separate DW Flow. "
        f"Read the authoritative strategy JSON at {strategy_relative}, the current outline at {project_relative}/{DYNAMIC_OUTLINE_FILENAME}, and the latest strategy validation report at {project_relative}/{DYNAMIC_STRATEGY_VALIDATION_FILENAME}. "
        "Treat the latest Dynamic Strategy Validation report as an explicit repair checklist, not as general feedback. For every parent, child, repeat/placement, or instruction item whose validation result is FAIL, identify the exact requirement in the authoritative JSON, locate its corresponding implementation in the current Dynamic Outline, and make the smallest semantic edit that causes the outline itself to satisfy that exact JSON requirement. A FAIL must be repaired in the corrected outline: do not merely discuss, acknowledge, summarize, restate, or promise to address it. "
        "Apply this repair procedure independently to every actionable FAIL in the latest report, including multiple FAILs within a single block or repeated group. When a required engagement placement exists but performs the wrong semantic function, rewrite that exact placement so it performs the JSON-requested function (for example, make a purported comment prompt actually invite comments). When a required instruction is missing from one item in a repeated group, add that instruction to that exact item rather than broadly rewriting the group. "
        "Before writing, internally self-audit the corrected outline against the latest report and JSON: every actionable FAIL must be repaired; every already-PASS block must remain semantically unchanged unless a tiny adjacent edit is unavoidable; and PASS WITH WARNING items must not be rewritten merely to remove warnings that are inherently unverifiable at outline stage. Revise the existing Dynamic Outline only to correct genuine strategy-validation defects and warnings that actually require an outline change. Preserve all already-correct content, ordering, evidence limits, factual grounding, and successful JSON implementations. "
        "The JSON remains the sole creative-strategy authority; the validation report diagnoses translation defects but cannot override or invent JSON requirements. Project evidence remains factual authority. "
        "RANKING PRECEDENCE: Explicit JSON instructions for ranking, a countdown, list order, or a ranking criterion control over the generic LIST PROGRESSION RULE, which applies only when the JSON leaves those matters unspecified. Do not cancel or convert an explicit ranked countdown to an unranked progression solely under that generic rule. Never invent an evidence hierarchy, medical superlative, or unsupported factual ranking; if an explicit JSON factual ranking criterion lacks project-evidence support, preserve the strategy-versus-evidence conflict visibly in the corrected outline. "
        "Do not add unsupported facts or medical claims. Do not solve timing-only warnings by inventing timestamps or fake timing evidence. Do not force changes for conditional warnings when the project evidence does not establish that the condition applies. "
        "Do not modify the strategy JSON, validation report, writer prompt, final script, QA, medical gate, or any old-pipeline file. Never read or use old 05_script_outline.md, old Opus Writer Prompt, old Narrative QA, old Medical Gate 2, or old workflow gates as authority. "
        f"Overwrite only {project_relative}/{DYNAMIC_OUTLINE_FILENAME} with the corrected complete writer-facing outline. Create no other artifact and output no process commentary."
    )


def _report_verdict(path: Path) -> str:
    if not path.is_file() or path.stat().st_size <= 0:
        return "MISSING"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return "ERROR"
    inline_pattern = re.compile(
        r"(?im)^\s*(?:#{1,6}\s*)?(?:[-*>]\s*)?(?:\*\*|__)?\s*"
        r"(?:overall\s+)?verdict\s*(?:\*\*|__)?\s*:\s*"
        r"(?:\*\*|__)?\s*(PASS WITH REVISIONS|PASS WITH WARNINGS|PASS|FAIL)\b",
    )
    match = inline_pattern.search(text)
    if match:
        return match.group(1).upper()
    heading_pattern = re.compile(
        r"(?im)^\s*#{1,6}\s+(?:overall\s+)?verdict\s*$",
    )
    heading = heading_pattern.search(text)
    if heading:
        following = text[heading.end():]
        next_verdict = re.search(
            r"(?im)^\s*(?:[-*>]\s*)?(?:\*\*|__)?\s*"
            r"(PASS WITH REVISIONS|PASS WITH WARNINGS|PASS|FAIL)\b",
            following,
        )
        if next_verdict:
            return next_verdict.group(1).upper()
    return "UNKNOWN"


def _strategy_validation_status(validation_path: Path, outline_path: Path) -> tuple[str, str]:
    if not validation_path.is_file() or validation_path.stat().st_size <= 0:
        return "MISSING", "Run Dynamic Strategy Validation before generating the Writer Prompt."
    if not outline_path.is_file() or outline_path.stat().st_size <= 0:
        return "MISSING", "Dynamic Outline is missing."
    if validation_path.stat().st_mtime < outline_path.stat().st_mtime:
        return "STALE", "The outline changed after the last validation. Run Dynamic Strategy Validation again."
    verdict = _report_verdict(validation_path)
    if verdict == "FAIL":
        return verdict, "Strategy validation failed. Fix the Dynamic Outline, then validate again before writing."
    if verdict in {"PASS", "PASS WITH WARNINGS"}:
        return verdict, f"Strategy validation cleared: {verdict}."
    return verdict, "Could not determine the strategy-validation verdict. Re-run validation."


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
        "Include this Ranking Authority and List Progression instruction in the finished writer prompt: explicit Dynamic JSON and Dynamic Outline instructions for ranking, a countdown, list order, or a ranking criterion are the highest creative-strategy authority and must be preserved. Apply the general List Progression instruction only when those Dynamic authorities leave ranking/order unspecified. Therefore, do not cancel an explicitly authorized ranked countdown merely because the generic default would prefer an unranked progression. Project evidence remains factual authority: never invent an evidence hierarchy, medical superlative, or unsupported factual ranking merely to justify a countdown. If an explicit Dynamic factual ranking criterion cannot be supported by project evidence, preserve the strategy-versus-evidence conflict visibly rather than silently converting the structure to unranked. When the default applies and a list is genuinely rankable with project evidence supporting a strongest/highest-value item, use one explicit evidence-supported ranking criterion consistently, make it clear to the viewer in the opening, progress toward #1 as the strongest evidence-supported payoff, tease that payoff early, and keep the opening item engaging rather than filler. Never create or intensify a health ranking around fear, danger, deadliness, or shock. When the default applies and the list is not genuinely rankable, never fabricate a hierarchy or call an item #1 most important; preserve the strongest natural progression and allow a surprising or useful final item without falsely claiming it ranks highest. "
        "Include this Disclaimer Replacement Rule in the finished writer prompt: do not repeatedly restate the same safety boundary, caveat, clinician-referral message, or not-medical-advice disclaimer, including paraphrased versions that serve the same semantic function. Give the full boundary once at the strongest natural location, then repeat only a brief claim-specific reminder when omitting it would make that particular claim materially misleading or unsafe. Do not use presenter identity as a substitute for evidence or safety context. Because the presenter is AI-generated, do not have it claim to be a human health educator, doctor, clinician, credentialed professional, or to possess personal clinical experience or qualifications. If presenter identification is requested, identify the channel or explain the video’s educational purpose neutrally without claiming personal credentials. Removing repetitive disclaimer text must not be used to shrink the script: preserve approximately the intended word budget by replacing that space with fresh evidence-supported viewer value from approved project research, such as explanation, practical interpretation, useful distinctions, examples, decision questions, mechanism or context, evidence limitations, or transitions. Never invent a fact, claim, statistic, mechanism, or recommendation merely to maintain word count, and never weaken a medically necessary safety boundary. "
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
        "Audit list progression when the script uses a list. Explicit ranking, countdown, list-order, or ranking-criterion instructions authorized by the Dynamic JSON or Dynamic Outline control; respect that requested structure and do not penalize or request removal of an authorized ranked countdown merely because the generic List Progression default would prefer an unranked progression. The generic default applies only when those Dynamic authorities leave ranking/order unspecified. For an explicitly authorized ranking, verify faithful order and criterion delivery without inventing factual support: project evidence remains factual authority, so flag any invented evidence hierarchy, medical superlative, or unsupported factual ranking, and require any explicit strategy-versus-evidence conflict to remain visible rather than silently converting the structure to unranked. When the generic default applies and a list is presented as ranked, verify that one explicit evidence-supported ranking criterion is clear in the opening, applied consistently, #1 is the strongest payoff under that criterion, the opening item is still engaging rather than filler, and the script does not rank health items by fear, danger, deadliness, shock, or another alarm criterion. When the generic default applies and the underlying items are not genuinely rankable from the approved evidence, flag any fabricated #1/most-important hierarchy; a surprising or useful final item is allowed without a ranking claim. Do not demand a countdown for a non-ranked list when Dynamic authority files do not request one. "
        "Audit disclaimer fatigue semantically, not only by exact wording. Group repeated passages that serve the same safety-boundary, caveat, clinician-referral, or not-medical-advice function even when paraphrased. For each repetition, classify whether the full boundary is needed once, a short claim-specific reminder is medically/narratively necessary, or the repetition is unnecessary. Do not require or reward a personal Health Educator identity statement. Because the presenter is AI-generated, flag claims that it is a human health educator, doctor, clinician, credentialed professional, or has personal clinical experience/qualifications; a neutral channel or educational-purpose introduction is acceptable. When recommending removal of unnecessary disclaimer repetition, do not simply shorten the script: require approximately the removed word budget to be replaced with fresh evidence-supported viewer value already available in approved project research, while preserving every medically necessary qualifier and never inventing new claims for padding. "
        "Distinguish necessary safety reminders from redundant reteaching. Check persona drift: the AI presenter must not claim to be a human health educator, doctor, clinician, credentialed professional, or to have personal clinical experience or qualifications. Flag invented first-person professional identity, patient-care, diagnosis, or prescribing claims. Neutral channel identification and evidence-focused educational framing are allowed. "
        "Markdown organizational headings are allowed as non-spoken structural markers. Do not flag, score down, or request removal of headings solely because the final narration should be spoken naturally; only flag a heading if its wording itself creates a genuine narrative defect. "
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


def _dynamic_speech_optimizer_prompt(project: Path) -> str:
    project_relative = project.relative_to(ROOT).as_posix()
    return (
        "Act as the isolated Dynamic Speech Optimizer for DW Flow. "
        f"Use {project_relative}/{DYNAMIC_FINAL_SCRIPT_FILENAME} as the sole canonical narration input. "
        f"Read {project_relative}/{DYNAMIC_NARRATIVE_QA_FILENAME} and {project_relative}/{DYNAMIC_MEDICAL_GATE_2_FILENAME} only to confirm both final gate verdicts are exactly PASS; do not reinterpret, bypass, or weaken those gates. "
        f"Create exactly two Production-compatible handoff files: {project_relative}/{VOICE_SCRIPT_FILENAME} and {project_relative}/{VOICE_CHECKLIST_FILENAME}. "
        f"In {VOICE_SCRIPT_FILENAME}, preserve every medical meaning, qualifier, negation, number, age, guideline attribution, safety distinction, CTA meaning, and approved wording from {DYNAMIC_FINAL_SCRIPT_FILENAME}. Do not add, remove, reorder, summarize, fact-check, strengthen, soften, or creatively rewrite claims. "
        "Perform delivery-only optimization for natural TTS/voice synthesis: remove non-spoken Markdown organizational headings and other non-spoken formatting, normalize smart quotes/dashes/ellipses/decorative Unicode conservatively, normalize repeated punctuation, use simple sentence punctuation where safe, expand only ordinary contractions when needed for synthesis clarity, and retain simple ASCII punctuation plus necessary intra-word hyphens for natural pacing/pronunciation. "
        "Attach pronunciation guidance only when needed and without changing the spoken wording or medical meaning. Never alter a technical term merely to make pronunciation easier. "
        f"In {VOICE_CHECKLIST_FILENAME}, document Speech QA, paragraph statistics, pronunciation review, chapter plan, upload checklist, and confirm that the source was {DYNAMIC_FINAL_SCRIPT_FILENAME} with Dynamic Narrative QA PASS and Dynamic Medical Gate 2 PASS. "
        "Do not read or modify the old Speech Optimizer implementation, its prompts, old final script, old Narrative QA, old Medical Gate 2, or any old workflow authority. Do not modify the Dynamic final script or any Dynamic gate report. "
        f"Write only {project_relative}/{VOICE_SCRIPT_FILENAME} and {project_relative}/{VOICE_CHECKLIST_FILENAME}; create no other artifact and no process commentary."
    )


def _dynamic_speech_gate_status(final_script_path: Path, qa_path: Path, mg2_path: Path) -> tuple[bool, str]:
    if not final_script_path.is_file() or final_script_path.stat().st_size <= 0:
        return False, f"{DYNAMIC_FINAL_SCRIPT_FILENAME} is missing or empty."
    if not qa_path.is_file() or qa_path.stat().st_size <= 0:
        return False, "Run Dynamic Narrative QA before the Dynamic Speech Optimizer."
    if qa_path.stat().st_mtime < final_script_path.stat().st_mtime:
        return False, "Dynamic Narrative QA is stale because the final script changed. Re-run Narrative QA."
    if not mg2_path.is_file() or mg2_path.stat().st_size <= 0:
        return False, "Run Dynamic Medical Gate 2 before the Dynamic Speech Optimizer."
    if mg2_path.stat().st_mtime < final_script_path.stat().st_mtime:
        return False, "Dynamic Medical Gate 2 is stale because the final script changed. Re-run Medical Gate 2."
    qa_verdict = _report_verdict(qa_path)
    mg2_verdict = _report_verdict(mg2_path)
    if qa_verdict != "PASS" or mg2_verdict != "PASS":
        return False, f"Dynamic Speech Optimizer requires exact PASS from both gates. Narrative QA: {qa_verdict}. Medical Gate 2: {mg2_verdict}."
    return True, "Dynamic Narrative QA: PASS · Dynamic Medical Gate 2: PASS · Production handoff is unlocked."


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

    validation_status, validation_message = _strategy_validation_status(strategy_validation_path, outline_path)
    if validation_status == "FAIL":
        st.error(validation_message)
        st.caption("Use the validation report to repair only the Dynamic Outline. The Writer Prompt remains locked until the repaired outline is validated again.")
        _run_generation("Fix Dynamic Outline from Validation", "dw_fix_dynamic_outline", "Applying strategy-validation corrections to the Dynamic Outline...", _dynamic_outline_fix_prompt(project), outline_path, f"Updated {DYNAMIC_OUTLINE_FILENAME}. Run Dynamic Strategy Validation again before writing.", codex_template)
    elif validation_status in {"PASS", "PASS WITH WARNINGS"}:
        st.success(validation_message)
    else:
        st.warning(validation_message)

    writer_prompt_path = project / DYNAMIC_WRITER_PROMPT_FILENAME
    writer_unlocked = validation_status in {"PASS", "PASS WITH WARNINGS"}
    if outline_path.is_file() and outline_path.stat().st_size > 0:
        st.markdown("### Generate Dynamic Writer Prompt")
        if writer_unlocked:
            st.caption("Strategy gate cleared. Builds a separate writer prompt from the validated Dynamic Outline; old Opus Writer Prompt is not used or modified.")
        else:
            st.caption("LOCKED: validate the current Dynamic Outline successfully before generating the Writer Prompt.")
        _run_generation("Generate Dynamic Writer Prompt", "dw_generate_dynamic_writer_prompt", "Generating Dynamic Writer Prompt from the validated Dynamic Outline...", _dynamic_writer_prompt(project), writer_prompt_path, f"Generated {DYNAMIC_WRITER_PROMPT_FILENAME} from the validated Dynamic Outline.", codex_template if writer_unlocked else "")
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

    st.markdown("### Dynamic Speech Optimizer")
    st.caption("Separate DW Flow optimizer. It does not use or modify the old Speech Optimizer. Its outputs intentionally use the existing Production handoff filenames.")
    speech_ready, speech_message = _dynamic_speech_gate_status(final_script_path, qa_path, mg2_path)
    if speech_ready:
        st.success(speech_message)
    else:
        st.warning(speech_message)
    voice_script_path = project / VOICE_SCRIPT_FILENAME
    voice_checklist_path = project / VOICE_CHECKLIST_FILENAME
    if st.button("Run Dynamic Speech Optimizer", type="primary", disabled=not (speech_ready and bool(codex_template)), key="dw_run_dynamic_speech_optimizer"):
        with st.spinner("Optimizing Dynamic narration for speech and creating Production-compatible handoff files..."):
            result = run_codex(codex_template, _dynamic_speech_optimizer_prompt(project), project, ROOT, RUN_LOG_DIR)
        outputs_ready = (
            voice_script_path.is_file() and voice_script_path.stat().st_size > 0
            and voice_checklist_path.is_file() and voice_checklist_path.stat().st_size > 0
        )
        if result.returncode == 0 and outputs_ready:
            st.success(f"Created {VOICE_SCRIPT_FILENAME} and {VOICE_CHECKLIST_FILENAME}. Existing Production can now use the standard handoff filenames.")
            st.rerun()
        elif result.returncode == 0:
            st.error(f"Dynamic Speech Optimizer finished but both {VOICE_SCRIPT_FILENAME} and {VOICE_CHECKLIST_FILENAME} were not created.")
            st.code(result.output or "No generator output returned.", language=None)
        else:
            st.error(f"Dynamic Speech Optimizer failed with exit code {result.returncode}.")
            st.code(result.output or "No generator output returned.", language=None)
    _show_markdown(voice_script_path, "Current Production Voice Script")
    _show_markdown(voice_checklist_path, "Current Production Voice Checklist")

st.info("Dynamic Outline, Strategy Validation, Writer Prompt, Narrative QA, Medical Gate 2, and Dynamic Speech Optimizer are isolated to DW Flow. The Dynamic Speech Optimizer alone hands off through 06a_voice_script.md and 06b_voice_checklist.md so the existing Production pipeline can continue unchanged.")

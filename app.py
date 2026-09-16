from __future__ import annotations

import csv
import json
import logging
import traceback
import os
import re
import shutil
import subprocess
import shlex
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from csv_safety import sanitize_csv_file
from production_sheet_contract import normalize_production_sheet, PRODUCTION_SHEET_COLUMNS, validate_scene_segmentation
from v31_core import (
    RUNTIME_ROUTING_CAUSES,
    canonical_runtime,
    parse_runtime_shortfall,
    record_runtime_redevelopment,
    runtime_config_conflicts,
    runtime_redevelopment_budget_spent,
    PIPELINE, WORKFLOW_STAGES, count_words, detect_codex_template,
    file_progress, get_gate_status, narrative_qa_ready, retention_structure_ready, next_action, production_lock,
    run_codex, save_uploaded_script, validate_final_script, validate_project, weighted_progress,
    apply_revision_patch, clean_production_script, ensure_production_cleaner, production_cleaner_prerequisites, production_cleaner_is_current, qa_dashboard, script_quality_metrics, stage_ready, validate_production_mix, production_outputs, sync_project_prompt_state, sync_project_validation_context, resolve_title_anchor, write_anchor_claim_map,
)

from avatar_timing import (
    avatar_sync_blockers, build_actual_timeline, chunk_sequence_info, discover_avatar_chunks,
    AvatarTranscriptionError, load_production_scenes, preflight_avatar_chunks, transcribe_avatar_chunks, transcription_settings, transcript_cache_is_current,
    transcript_inventory,
)
from timeline_builder import TimelineBuildError, build_timeline_manifest
from capcut_export import CapCutExportError, export_capcut_project
from semantic_coherence import enforce_final_semantic_report
from image_generation import (
    DEFAULT_MODEL_KEY, build_images_zip, enhance_prompt, generate_batch, load_manifest,
    load_production_image_assignments, model_profiles_from_config, reconcile_manifest,
    select_failed_or_missing, select_missing, select_stale,
)
from opus_image_prompt_import import load_production_ai_image_slots, validate_import, write_image_prompts
from text_overlay import ARTIFACT_NAME, parse_opus_csv, validate_rows, write_artifact
from analytics_db import (
    AnalyticsDBError, init_db, ensure_project_record, register_youtube_only_video, update_video_identity, snapshot_actual_timeline, snapshot_timestamped_transcript, import_youtube_csv, list_videos, get_video, latest_performance, scene_snapshot_df, mark_missing_project_folders, bulk_import_channel_content_csv, auto_link_existing_projects, link_youtube_record_to_project, needs_transcript_upload, weekday_performance_summary, channel_dashboard_data, winner_loser_learning_data, import_retention_curve, retention_points_df, scene_retention_mapping, retention_drop_summary, script_retention_learning, cross_video_script_pattern_learning, active_channel_script_rules, all_channel_script_rules, sync_active_channel_script_rules, render_active_channel_rules_markdown, write_active_channel_rules_file, repair_reconstructed_transcript_overlaps, production_learning_scene_df, production_learning_summary, production_provenance, bind_youtube_video_id_to_project, thumbnail_inventory_df, thumbnail_analysis_df, join_thumbnail_ctr_evidence, join_all_thumbnail_ctr_evidence, thumbnail_ctr_evidence_df, build_thumbnail_packaging_comparisons, thumbnail_packaging_associations_df, sync_packaging_rule_candidates, all_channel_packaging_rules, set_packaging_rule_status, write_active_packaging_rules_file, packaging_rule_promotion_audit, promote_packaging_signal_cluster,
)
from thumbnail_assets import download_thumbnail_snapshot, download_missing_thumbnails
from thumbnail_learning_sync import auto_sync_thumbnail_learning
from thumbnail_analysis import analyze_thumbnail_snapshot, analyze_pending_thumbnails
from thumbnail_concept_validation import validate_thumbnail_concepts
from youtube_api_sync import (
    YouTubeAPIError, connection_status as youtube_connection_status,
    start_manual_oauth, sync_youtube_channel,
)

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
PROJECTS_DIR = ROOT / "Projects"
ANALYTICS_DIR = ROOT / "Analytics"
ANALYTICS_DB_PATH = ANALYTICS_DIR / "senior_health_analytics.db"
ACTIVE_CHANNEL_RULES_PATH = ANALYTICS_DIR / "active_channel_script_rules.md"
ACTIVE_CHANNEL_PACKAGING_RULES_PATH = ANALYTICS_DIR / "active_channel_packaging_rules.md"
YOUTUBE_OAUTH_CLIENT_PATH = ANALYTICS_DIR / "youtube_oauth_credentials.json"
YOUTUBE_OAUTH_TOKEN_PATH = ANALYTICS_DIR / "youtube_oauth_token.json"
YOUTUBE_OAUTH_PENDING_PATH = ANALYTICS_DIR / "youtube_oauth_pending.json"
RUN_LOG_DIR = ROOT / "RunLogs"

EDITABLE_SUFFIXES = {".md", ".txt", ".json"}
VIEWABLE_SUFFIXES = {".md", ".txt", ".csv", ".json"}


@dataclass
class ProjectStatus:
    name: str
    path: Path
    present: int
    total: int
    missing: list[str]

    @property
    def percent(self) -> int:
        return round((self.present / self.total) * 100) if self.total else 0


def safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8-sig")
    except (FileNotFoundError, OSError):
        return ""


def validate_production_sheet_against_voice(project: Path) -> tuple[bool, list[str]]:
    """Validate ONLY narration provenance/order against 06a_voice_script.md.

    Scene-size/timing QA is intentionally separate. Avatar Timing must not report a
    stale-script mismatch merely because a scene is short/long or has provisional
    timing that the production planner should improve.
    """
    voice_path = project / "06a_voice_script.md"
    sheet_path = project / "07_production_sheet.csv"
    if not voice_path.is_file() or not sheet_path.is_file():
        return False, ["06a_voice_script.md and 07_production_sheet.csv are required for source validation."]
    voice = safe_read_text(voice_path)
    normalize = lambda value: re.sub(r"\s+", " ", value).strip()
    voice_norm = normalize(voice)
    cursor = 0
    issues: list[str] = []
    with sheet_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return False, ["07_production_sheet.csv has no production scenes."]
    for index, row in enumerate(rows, 1):
        scene_id = str(row.get("scene_id") or row.get("Scene ID") or f"S{index:03d}").strip()
        excerpt = normalize(str(row.get("script_excerpt") or row.get("Script Text") or row.get("narration") or ""))
        if not excerpt:
            issues.append(f"{scene_id}: script_excerpt is empty.")
            continue
        pos = voice_norm.find(excerpt, cursor)
        if pos < 0:
            anywhere = voice_norm.find(excerpt)
            if anywhere >= 0:
                issues.append(f"{scene_id}: script_excerpt is out of source order.")
            else:
                issues.append(f"{scene_id}: script_excerpt is not an exact excerpt of current 06a_voice_script.md.")
        else:
            cursor = pos + len(excerpt)
    return not issues, issues


def production_sheet_segmentation_issues(project: Path) -> list[str]:
    """Return semantic scene/timing QA issues without conflating them with source provenance."""
    sheet_path = project / "07_production_sheet.csv"
    if not sheet_path.is_file():
        return ["07_production_sheet.csv is missing."]
    try:
        with sheet_path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as exc:
        return [f"Could not read 07_production_sheet.csv: {exc}"]
    return validate_scene_segmentation(rows)

def clear_stale_production_outputs(project: Path) -> list[str]:
    """Remove only regenerated Production-package outputs before a fresh run."""
    removed: list[str] = []
    for name in ("07_production_sheet.csv", "10_image_prompts.md", "12_broll_prompts.md"):
        path = project / name
        if path.is_file():
            try:
                path.unlink()
                removed.append(name)
            except OSError as exc:
                raise RuntimeError(f"Close {name} before regenerating Production: {exc}") from exc
    return removed


def safe_write_text(path: Path, text: str) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        return True
    except OSError as exc:
        st.error(f"Could not save {path.name}: {exc}")
        return False


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(safe_read_text(CONFIG_PATH))
    except json.JSONDecodeError:
        return {}


def save_config(config: dict[str, Any]) -> None:
    safe_write_text(CONFIG_PATH, json.dumps(config, indent=2, ensure_ascii=False) + "\n")


def slugify_topic(topic: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower().strip())
    return re.sub(r"-+", "-", slug).strip("-") or "untitled-project"


def project_dirs() -> list[Path]:
    PROJECTS_DIR.mkdir(exist_ok=True)
    return sorted((p for p in PROJECTS_DIR.iterdir() if p.is_dir()), key=lambda p: p.name.lower())


def get_project_status(project: Path) -> ProjectStatus:
    missing = [file_name for _, file_name in PIPELINE if not (project / file_name).exists()]
    return ProjectStatus(project.name, project, len(PIPELINE) - len(missing), len(PIPELINE), missing)


def project_selector(key: str) -> Path | None:
    projects = project_dirs()
    if not projects:
        st.info("No projects found. Create one from New Project.")
        return None
    name = st.selectbox("Project", [p.name for p in projects], key=f"project_{key}")
    return PROJECTS_DIR / name


def command_for_stage(project: Path, stage: str, anchor_outlier_pattern: str | None = None) -> str:
    ref = f"Projects/{project.name}/"
    commands = {
        "Topic Validation": f"Run Stage 1 only for {ref}. Read project.json.anchor_title first and treat that exact Anchor / Outlier Title as the immutable, already-approved winning title and sole wording authority. Follow the Topic Validation policy in Agents/Outlier_Agent.md. Treat 01a_anchor_claim_map.json only as supporting parser context, never as the evidence verdict. Research the topic deeply enough to establish the evidence-supported production angle, payoff, boundaries, demand, and safety without reopening title generation or rewriting. Create only 01_topic_validation.md; preserve project.json and 01a_anchor_claim_map.json unchanged. Stop after validation.",
        "Research + Medical Gate 1": f"For {ref}, run Research_Agent and Medical_Agent Gate 1 using the exact immutable, already-approved project.json.anchor_title and the Stage 1 handoff in 01_topic_validation.md. Follow the role-boundary policies in Agents/Research_Agent.md and Agents/Medical_Agent.md: research and medically validate the content claims, production angle, evidence limits, and safety boundaries without re-adjudicating, repairing, replacing, or failing the title itself. Treat 01a_anchor_claim_map.json only as parser context. Create only 02_research_sheet.md and 13_fact_check_log.md, then stop before creative work.",
        "Thumbnail": f"For {ref}, run Thumbnail_Agent only using approved upstream files. Use project.json.anchor_title EXACTLY as the winning title; do not generate, rank, rewrite, repair, or replace the title. BEFORE generating concepts, read Analytics/active_channel_packaging_rules.md when present and apply every ACTIVE packaging rule that is contextually applicable to this project. When that artifact contains matching historical channel examples, derive thumbnail text structure/hierarchy AND visual/color packaging from those real channel patterns BEFORE inventing generic concepts; adapt the pattern to this topic and never copy old wording verbatim. In 04_thumbnail_concepts.md, include a mandatory `Historical Channel Examples Used` audit section listing 3-5 actual consumed examples per applicable ACTIVE rule (or all if fewer), with exact historical thumbnail text, source video/title, CTR, impressions, relevant text structure/hierarchy, relevant visual/color traits, and what was adapted. If no examples exist, state `NO MATCHING HISTORICAL EXAMPLES AVAILABLE` and do not claim an example-derived historical pattern. Treat learned packaging rules as impression-aware historical associations, never causal guarantees. They may guide thumbnail text/visual packaging only and must never override the immutable title promise, approved research/evidence, Medical Gate requirements, medical safety, or project-specific creative fit. Ignore CANDIDATE, REJECTED, and RETIRED rules; only the ACTIVE rules artifact may be injected. If an ACTIVE rule is not applicable to the current hero/category/context, mark it N/A rather than forcing it. For any digestion/anatomy visual, preserve one physiologically coherent continuous route; never render multiple colored internal pathways, branching arrows through organs, glowing nutrient streams, or magic-path effects unless explicitly supported by approved evidence. Create only 04_thumbnail_concepts.md and 11_thumbnail_prompt.md.",
        "Script Outline": f"For {ref}, run Script_Agent in outline_to_script mode. Use project.json.anchor_title EXACTLY as the immutable winning title and align the complete outline to its promise; do not generate or substitute another title. BEFORE outlining, read Analytics/active_channel_script_rules.md when present and apply every ACTIVE learned writing rule that does not conflict with the immutable title, approved evidence/research, Medical Gate requirements, or necessary safety language. Learned rules control pacing/structure only and may never override medical accuracy. Create only 05_script_outline.md. Do not create 06_final_script.md.",
        "Prepare Opus Package": f"For {ref}, prepare a fresh per-project opus_writer_package.md from the current writing templates and 05_script_outline.md. BEFORE building the package, read Analytics/active_channel_script_rules.md when present. Read Templates/Writing/opus_writer_prompt.md in full. HARD PRESERVATION RULE: copy the complete `## Semantic Progression Lock`, `## Retention-First Drafting Lock`, and `## Execution / No-Negotiation Lock` sections from Templates/Writing/opus_writer_prompt.md into opus_writer_package.md without summarizing, weakening, paraphrasing, or omitting their rules. Also preserve the Execution / No-Negotiation rule that the writer must draft first without pre-negotiating research sufficiency, predicted word capacity, target feasibility, or asking for more research merely to reach runtime. RUNTIME PACKAGE LOCK: do not place any automatic runtime target, runtime range, WPM target, word-count target/range, minimum, maximum, floor, validation boundary, required word adjustment, or numeric drafting target in opus_writer_package.md. Runtime and word count cannot influence drafting, revision, expansion, compression, research/source requests, claims, or upstream routing. The writer must write the strongest complete script supported by approved evidence, then report actual word count/runtime afterward as informational metadata only with `Runtime Advisory: ADVISORY ONLY — NON-BLOCKING`. In particular, preserve the full material-delta semantics: a different example/food/section, new wording, another hypothetical, or repeated safety/scope reminder is not sufficient new value; if no concrete material delta exists, omit or merge the recurrence; allow at most one concise final recap that compresses rather than reteaches. Include a clearly labeled ACTIVE CHANNEL SCRIPT RULES section in opus_writer_package.md and require the writer to apply those rules unless they conflict with the immutable winning title, approved research/evidence, Medical Gate requirements, or necessary safety language. Learned retention rules may improve pacing/structure but may never override medical accuracy. Create or update only opus_writer_package.md.",
        "Writer Workspace": f"Manual stage for {ref}. Download opus_writer_package.md, write the full script in Claude, then upload the result through Writer Workspace as 06_final_script.md. Direct Codex Run is intentionally disabled for this manual stage.",
        "Retention Structure Analysis": f"For {ref}, run ONLY the Retention Structure Analyzer. Read the complete current 06_final_script.md and project.json.anchor_title. Read Templates/Writing/retention_structure_analyzer.md and obey it exactly. Also read Analytics/active_channel_script_rules.md when present and verify EACH currently ACTIVE rule against the actual current 06_final_script.md. Include the required ACTIVE CHANNEL RULE COMPLIANCE table with PASS/FAIL/N/A, a 5–8+ word verbatim script anchor, concise reason, and corrective H/O/P/R/C/B patch IDs for failures when safely fixable. Do not count rule injection into the writer package as implementation evidence. Analyze structure and pacing only; do not judge medical correctness and do not modify 06_final_script.md, facts, evidence, numbers, medical claims, required safety language, or the immutable winning title. Create or replace ONLY retention_structure_analysis.md in the selected project root. The report must use Status: READY or Status: NEEDS REVISION, include the one-line Retention Risk Reason, unique H/O/P/R/C/B patch IDs, 5–8+ word verbatim anchors, relevant timestamp/word-position estimates, adaptive pacing signals, execution sequence, verification table, copy-ready Script Chat Revision Prompt, and the required unchanged-substance footer. Stop after writing retention_structure_analysis.md.",
        "Narrative QA": f"For {ref}, run Narrative_QA_Agent using 05_script_outline.md, 02_research_sheet.md when present, 13_fact_check_log.md when present, retention_structure_analysis.md when present, 06_final_script.md, config.json, the Narrative QA templates, and Analytics/active_channel_script_rules.md when present. Independently audit the CURRENT final script for storytelling, pacing, semantic repetition, whole-script recurrence, information progression, title-payoff timing, redundant recap/ending cycles, safety-boundary consolidation, transitions, tone, CTA placement, non-blocking evidence-review flags, and approved blueprint order. Treat the Retention Structure report as prior context, not proof; do not treat writer-package injection or the earlier Retention report as proof of implementation. Verify EACH currently ACTIVE rule against the current script with PASS/FAIL/N/A, a verbatim anchor, reason, and revision-required status; a learned-rule FAIL is evidence to inspect, not automatically an overall FAIL. Keep density separate from progression: paragraph length or several sourced facts alone are not a hard failure when the beat adds concrete new viewer value. MATERIAL-DELTA TEST: apply a MATERIAL-DELTA TEST to every post-primary occurrence for repeated core ideas; later occurrences must add exact new viewer knowledge/decision/mechanism/consequence/evidence/action, except one concise final recap; any post-primary occurrence with no concrete material delta must be CUT/MERGED. EVIDENCE REVIEW HANDOFF — NON-BLOCKING: classify factual additions as Type A material factual claims, Type B source-faithful explanatory paraphrases, or Type C narrative connectives for auditability. If a Type A proposition lacks an explicit approved trace, mark EVIDENCE REVIEW FLAG — SOURCE TRACE: NONE and KEEP — MG2 REVIEW. Missing provenance alone MUST NOT cause CUT/MERGE, Revision Patch, PASS WITH REVISIONS, or FAIL in Narrative QA; Medical Gate 2 / Fact Check owns that evidence decision. Narrative QA may revise the same sentence only for an independent narrative defect and must name that narrative defect. Type B may use EXPLANATORY PARAPHRASE — TRACE: <source>; Type C may use NARRATIVE CONNECTIVE — NO SOURCE REQUIRED. BLUEPRINT ORDER GATE: compare the current major sequence with 05_script_outline.md and authorized retention changes; unresolved unapproved major reorder cannot PASS. RUNTIME ADVISORY-ONLY LOCK: runtime, word count, configured minimum/target/maximum, WPM, and runtime tolerance MUST NOT determine PASS / PASS WITH REVISIONS / FAIL. Runtime must never cause a revision, expansion, compression, source-pool audit, redevelopment route, or another QA cycle. Count spoken narration only and include one compact ## Runtime Advisory with current narration words, estimated runtime at config.json WPM, preferred configured range, BELOW/INSIDE/ABOVE position, and the exact statement 'QA effect: NONE — runtime is advisory and cannot change the Narrative QA verdict.' Do not output Runtime Shortfall Cause, Remaining Approved Material Audit, Runtime Prediction, Convergence Check, required word adjustment, or runtime-driven patch. Every Revision Patch must identify a concrete narrative or safety-placement defect that would still exist if runtime and missing source provenance were ignored, and use the minimum necessary correction. Missing source provenance alone can never be a patch reason. Create 14_narrative_qa.md with Status: PASS / PASS WITH REVISIONS / FAIL based ONLY on narrative-quality, structure, repetition/progression, payoff, and safety-placement gates; evidence-review flags are handed to Medical Gate 2 and are non-blocking here. Include required Semantic Progression Gate with Material delta vs primary and Approved source trace columns, Approved Blueprint Order Audit, Active Channel Rule Compliance, Issue List, Revision Patch when needed, and Runtime Advisory. Repetition Risk HIGH, unresolved semantic recurrence above threshold, unresolved redundant endings/recaps, materially delayed title payoff, unresolved 2+ consecutive low-progression beats, or unresolved blueprint-order defects cannot PASS. Evidence Review Flags never block Narrative QA and proceed to Medical Gate 2 / Fact Check. Do not estimate AVD percentages. Do not directly rewrite 06_final_script.md.",
        "Medical Gate 2": f"For {ref}, run Medical_Agent Gate 2 after Narrative QA PASS or PASS WITH REVISIONS. Compare every medical statement in 06_final_script.md against 02_research_sheet.md and 13_fact_check_log.md. Create 15_medical_gate_2.md with Status: PASS / PASS WITH REVISIONS / FAIL. When edits are required, include a structured Revision Patch using Section:, Current Text:, Replace With:, Reason:, Severity:. Update 13_fact_check_log.md only when necessary. Do not directly rewrite the script or run production.",
        "Speech Optimizer": f"For {ref}, run the Speech Optimizer only after Narrative QA and Medical Gate 2 both report exactly PASS. Do not bypass, ignore, or reinterpret those upstream gates; PASS WITH REVISIONS / PASS WITH SUGGESTIONS / FAIL are not sufficient. Use the current approved 06_final_script.md as the canonical input and Templates/Voice/ only for speech/delivery optimization. Create only 06a_voice_script.md and 06b_voice_checklist.md. The checklist must include Speech QA, Paragraph Statistics, Pronunciation Review, Chapter Plan, and Upload Checklist. Do not modify 06_final_script.md.",
        "Production Package": f"For {ref}, 06a_voice_script.md is the ONLY authoritative source for narration and scene text. Read that file fresh from disk before planning scenes. Do NOT read, reuse, infer narration from, or copy scene text from 05_script_outline.md, 06_final_script.md, 06_final_script_locked.md, any prior 07_production_sheet.csv, 08_actual_timeline.csv, old image/B-roll prompts, run logs, caches, or any other project editorial artifact. Start Production without checking any prior editorial workflow stage, gate, checklist, title, research, outline, final-script, or production-cleaner status. Preserve the supplied narration exactly: every 07_production_sheet.csv script_excerpt must be an exact contiguous excerpt from the current 06a_voice_script.md and scene excerpts must follow source order without invented/paraphrased script lines. Respect production_settings.json. Use VIDEO_PROMPT_TEMPLATE_ULTIMATE.md only as the narrative-context/prompt-quality framework; ignore its legacy 8-second/WPM/image-count/batching allocation rules. The NEW 07_production_sheet.csv created in this run becomes authoritative for AI_IMAGE slots and assignment order. Preserve image_001.png assignment-order naming. Run the system-level semantic Visual Diversity Engine with a project-local Visual Diversity Ledger: derive Core Visual Signatures, discover project-local visual families, and enforce config-driven semantic duplicate/rolling/family-balance thresholds through the bounded QA -> rewrite -> signature recalculation convergence loop. Do not finalize 10_image_prompts.md until diversity reaches PASS or a justified unresolved FAIL is documented. A similarity of 1.00 may never remain Rewritten: NO without explicit Intentional Repetition: YES plus reason. Rewrite core concepts rather than camera/location variants, reset the ledger per project, and emit the full semantic Visual Diversity QA. After diversity convergence, run the Final Semantic Coherence Guard against original Script Context, Narrative Context, preceding visual, following visual, AND the final rendered prompt text itself; infer normalized temporal/lighting with explicit time-of-day consistency, setting/action compatibility, object/location, scene-purpose/structural-role, and emotional-tone attributes and reject contradictions even when metadata appears compatible. Explicitly detect final-prompt temporal contradictions such as night/bedtime context paired with morning/daybreak lighting, and the inverse, by semantic compatibility rather than a fixed phrase blacklist. Reject incoherent diversity rewrites, correct them within configured semantic_coherence retry bounds, recalculate affected diversity signatures/families after every coherence correction, and require BOTH Overall Visual Diversity: PASS and Overall Semantic Coherence: PASS before marking 10_image_prompts.md production-ready. Continue diversity convergence while unjustified near-duplicate candidates remain above configured limits; if retry bounds are exhausted, keep FAIL, enumerate exact unresolved image IDs, and emit Production Ready: NO rather than silently treating the diagnostic file as ready. Classify discourse role before prompt generation: host sign-off/episode-close terminal narration is STRUCTURAL_CLOSE; other CTA/subscribe/transition narration may be STRUCTURAL when appropriate. STRUCTURAL_CLOSE must not inherit recurring topic imagery unless the exact closing narration requires it. After all rewrites, run the deterministic final-output semantic verifier over final prompt text; any detected conflict overrides a stale PASS and forces exact-image reporting plus Production Ready: NO. For every AI_IMAGE candidate, treat exact current Script Context as primary authority, immediate previous/following Narrative Context second, then visual clarity, human realism, diversity, and camera/composition variation. Before accepting the final rendered prompt, apply the muted-audio semantic test: if shown without audio, would its main subject/action reasonably illustrate the narration being spoken? Emit Alignment Score: 0-100 for every image and require >=85. Below 85, rewrite the visual concept from Script Context itself; camera/style-only rewrites do not count. Never solve repetition by substituting an unrelated archetype; allow repeated objects when the narration genuinely requires them. Prefer documented intentional repetition over a less relevant visual. SEMANTIC SCENE SPLIT IS A HARD GATE: segment 06a_voice_script.md by coherent visual/narrative idea BEFORE assigning the production mix. Do not target a fixed scene count. Do not create/split/merge rows to satisfy 40/30/20/10 or any other mix. Normal scenes are roughly 8-28 spoken words; merge orphan fragments under 4 words with an adjacent beat unless notes explicitly marks INTENTIONAL_EMPHASIS; split multi-idea excerpts above roughly 34 words. A phrase such as `Just five.` must never receive a padded 6-second standalone slot by default. Provisional duration must come from narration length/natural speech, and start_time/end_time must be elapsed M:SS (e.g. 26:35), never 26:35:00. After semantic scene boundaries are frozen, apply production_settings.json only as an approximate asset-type distribution over those scenes. HARD CSV CONTRACT: 07_production_sheet.csv MUST use the existing canonical 32-column header exactly and in order: scene_id,start_time,end_time,duration_sec,scene_purpose,script_excerpt,visual_mode,avatar_required,avatar_style,background_style,image_prompt_id,broll_prompt_id,narrative_context,visual_intent,filmable,asset_decision_reason,asset_search_query,alternative_search_query_1,alternative_search_query_2,ai_image_prompt,overlay_instruction,recommended_asset_type,recommended_shot,manual_search_notes,avoid_results,asset_source,selected_asset_path,asset_status,motion,transition,on_screen_text,notes. Populate the rich production data for every row; never emit compact slot_id/slot_type/asset_type schemas. recommended_asset_type must use STOCK_VIDEO/STOCK_IMAGE/AI_IMAGE/AVATAR/OVERLAY/SPLIT_SCREEN/NO_ASSET_NEEDED. AI_IMAGE rows require sequential IMG001.. IDs and non-empty ai_image_prompt; stock rows require sequential BR001.. IDs and concrete queries. Create only 07_production_sheet.csv, 10_image_prompts.md, and 12_broll_prompts.md. AI prompts only for AI_IMAGE scenes.",
        "SEO": f"For {ref}, run SEO_Agent only after the approved script and final 08_actual_timeline.csv exist. Use project.json.anchor_title EXACTLY as the final/winning YouTube title; do not optimize, rewrite, rank, or replace it. Create or update only 08_youtube_metadata.md. For ## 5. Chapters / Timestamps, emit semantic chapter labels with S### scene anchors only; deterministic application code replaces them with Actual Audio Start timestamps from 08_actual_timeline.csv.",
        "Final QA + Summary": f"For {ref}, run Final QA only. Check all required outputs, narrative QA, Medical Gate 2, host identity, metadata, and production files. Create or update only 09_qa_checklist.md and 16_project_summary.md. Do not silently rewrite approved content.",
    }
    return commands[stage]




def detect_codex_command() -> str:
    return detect_codex_template(load_config())


def _artifact_signature(path: Path) -> tuple[int, int] | None:
    if not path.is_file():
        return None
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size


OPUS_RUNTIME_ADVISORY_TEXT = "Runtime Advisory: ADVISORY ONLY — NON-BLOCKING"
OPUS_STALE_RUNTIME_PATTERNS = (
    r"configured\s+validation\s+range",
    r"validation\s+(?:runtime\s+)?(?:range|floor|boundary|boundaries)",
    r"configured\s+(?:runtime\s+)?(?:minimum|maximum|floor)",
    r"(?:under|below|reach|meet|toward)\s+(?:the\s+)?(?:runtime\s+)?floor",
    r"soft\s+planning\s+(?:target|reference)",
    r"planning\s+runtime\s+reference\s*:\s*\d",
    r"\b\d{1,3}(?:,\d{3})?\s*(?:[–-]|to)\s*\d{1,3}(?:,\d{3})?\s+words\b",
    r"\bruntime\s*:\s*\d+(?:\.\d+)?\s+minutes?\b",
    r"\bapproximately\s+\d{1,3}(?:,\d{3})?\s+words?\s+at\s+\d+\s+WPM\b",
    r"\b(?:expand|increase|lengthen)\s+(?:the\s+)?(?:draft|script|word\s+count|length)\b",
    r"\b(?:additional|more)\s+(?:approved\s+)?(?:research|sources?|claims?)(?:/claims?)?\s+to\s+(?:increase|reach|meet)\b",
)


def opus_writer_package_runtime_issues(project: Path) -> list[str]:
    """Validate the actual generated Writer package against the advisory-only lock."""
    path = Path(project) / "opus_writer_package.md"
    if not path.is_file() or path.stat().st_size == 0:
        return ["opus_writer_package.md is missing or empty."]
    text = safe_read_text(path)
    issues: list[str] = []
    if OPUS_RUNTIME_ADVISORY_TEXT not in text:
        issues.append(f"Missing exact runtime lock: {OPUS_RUNTIME_ADVISORY_TEXT}")
    for pattern in OPUS_STALE_RUNTIME_PATTERNS:
        match = re.search(pattern, text, re.I)
        if match:
            issues.append(f"Stale Writer-package runtime semantics detected: {match.group(0)}")
    return issues

def run_external_command(command_template: str, prompt: str, project: Path, title_anchor_outlier_pattern: str | None = None, manual_titles: list[str] | None = None, stage: str | None = None):
    # Title generation/judging has been removed. Every active stage reads the immutable
    # user-supplied winning title from project.json.anchor_title.
    #
    # Thumbnail pattern learning must be refreshed at the moment the Thumbnail Agent
    # runs. A user may promote an ACTIVE packaging rule after the last YouTube sync;
    # relying on a previously-written markdown artifact would make the agent see stale
    # rules without the newly-available historical examples. Re-rendering here is
    # read-only with respect to analytics evidence and keeps ACTIVE decisions intact.
    is_thumbnail_run = stage == "Thumbnail" or (stage is None and "run Thumbnail_Agent" in prompt)
    if is_thumbnail_run and ANALYTICS_DB_PATH.exists():
        try:
            write_active_packaging_rules_file(ANALYTICS_DB_PATH, ACTIVE_CHANNEL_PACKAGING_RULES_PATH)
        except (AnalyticsDBError, OSError, ValueError):
            # Do not block creative generation if analytics is temporarily unavailable;
            # preserve and use the last valid ACTIVE artifact instead.
            pass
    result = run_codex(command_template, prompt, project, ROOT, RUN_LOG_DIR)
    is_opus_package_run = stage == "Prepare Opus Package" or (
        stage is None and "prepare a fresh per-project opus_writer_package.md" in prompt
    )
    if result.returncode == 0 and is_opus_package_run:
        package_issues = opus_writer_package_runtime_issues(project)
        if package_issues:
            result.returncode = 2
            result.output = (
                result.output
                + "\n\nOpus Writer package runtime contract: FAIL\n"
                + "\n".join(f"- {issue}" for issue in package_issues)
            )[-20000:]
        else:
            result.output = (result.output + "\n\nOpus Writer package runtime contract: PASS")[-20000:]
    is_seo_run = stage == "SEO" or (stage is None and "run SEO_Agent" in prompt)
    if result.returncode == 0 and is_seo_run:
        from seo_chapters import SEOChapterError, finalize_project_seo
        from analytics_db import AnalyticsDBError, archive_production_learning_checkpoint

        # Archive is an independent SEO-time checkpoint. A chapter-formatting
        # problem must never prevent the final production/timeline snapshot from
        # being preserved for analytics learning.
        try:
            checkpoint = archive_production_learning_checkpoint(ANALYTICS_DB_PATH, project)
            result.output = (
                result.output
                + "\n\nProduction learning archive: PASS"
                + f"\nAnalytics ID: {checkpoint['analytics_id']}"
                + f"\nMerged scenes: {checkpoint['merged_rows']}"
                + "\nTiming authority: 08_actual_timeline.csv"
            )[-20000:]
        except (AnalyticsDBError, OSError, ValueError) as exc:
            result.returncode = 2
            result.output = (result.output + f"\n\nProduction learning archive: FAIL\n{exc}")[-20000:]

        # Preserve the existing deterministic SEO chapter finalizer as a
        # separate concern. It may fail SEO, but it no longer blocks archival.
        try:
            diagnostics = finalize_project_seo(project)
            if diagnostics:
                result.output = (result.output + "\n\nSEO chapter finalizer:\n" + "\n".join(diagnostics))[-20000:]
        except SEOChapterError as exc:
            result.returncode = 2
            result.output = (result.output + f"\n\nSEO chapter finalization: FAIL\n{exc}")[-20000:]
    return result

def system_version() -> str:
    """Single source of truth for the displayed version: config.json system_version."""
    return str(load_config().get("system_version", "")).strip() or "3.4"


def inject_css() -> None:
    st.markdown("""
    <style>
    .block-container {padding-top: 1.2rem; padding-bottom: 3rem;}
    div[data-testid="stMetric"] {border:1px solid rgba(120,120,120,.22); border-radius:14px; padding:12px;}
    .stage-card {border:1px solid rgba(120,120,120,.22); border-radius:14px; padding:12px 14px; margin-bottom:8px;}
    .ok {color:#18a558;font-weight:700}.wait {color:#cc8a00;font-weight:700}
    </style>
    """, unsafe_allow_html=True)


def render_dashboard() -> None:
    st.subheader(f"V{system_version()} Production Dashboard")
    config = load_config()
    projects = project_dirs()
    if not projects:
        st.info("No projects yet.")
        return
    rows = []
    for project in projects:
        present, total, files_pct = file_progress(project)
        lock = production_lock(project, config)
        rows.append({
            "Project": project.name, "Progress": weighted_progress(project, config),
            "Files": f"{present}/{total}", "Next Action": next_action(project, config),
            "Production": "LOCKED" if lock.locked else "READY",
        })
    df = pd.DataFrame(rows)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Projects", len(df))
    c2.metric("Average progress", f"{round(df['Progress'].mean())}%")
    c3.metric("Production ready", int((df["Production"] == "READY").sum()))
    c4.metric("Locked", int((df["Production"] == "LOCKED").sum()))
    st.dataframe(df, hide_index=True, width="stretch", column_config={"Progress": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d%%")})

    selected = project_selector("dashboard")
    if selected:
        pct = weighted_progress(selected, config)
        st.progress(pct / 100, text=f"Weighted workflow progress: {pct}%")
        lock = production_lock(selected, config)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Writer Workspace", "VALID" if validate_final_script(selected, config).valid else "BLOCKED")
        c2.metric("Narrative QA", get_gate_status(selected, "Narrative QA", config).status)
        c3.metric("Medical Gate 2", get_gate_status(selected, "Medical Gate 2", config).status)
        c4.metric("Production Lock", "LOCKED" if lock.locked else "OPEN")
        if lock.locked:
            st.error("Production is locked: " + " ".join(lock.reasons))
        st.markdown("### Workflow")
        for stage, filename in PIPELINE:
            exists = (selected / filename).exists()
            label, css = ("READY", "ok") if exists else ("PENDING", "wait")
            extra = ""
            if filename in {config.get("narrative_qa_output", "14_narrative_qa.md"), config.get("medical_gate_2_output", "15_medical_gate_2.md")} and exists:
                extra = f" · {get_gate_status(selected, stage, config, filename=filename).status}"
            st.markdown(f'<div class="stage-card"><span class="{css}">{label}</span> &nbsp; <b>{stage}</b>{extra}<br><small>{filename}</small></div>', unsafe_allow_html=True)



def _normalize_pre_title_payload(value: Any) -> dict[str, Any] | None:
    """Return a normalized advisory payload from structured Codex output."""
    if isinstance(value, dict):
        overall = str(value.get("overall", value.get("status", value.get("verdict", "")))).strip().upper().replace("_", " ").replace("-", " ")
        if overall in {"PASS", "REVIEW", "HIGH RISK"}:
            value = dict(value)
            value["overall"] = overall
            value["summary"] = str(value.get("summary", value.get("reason", ""))).strip()
            checks = value.get("checks", value.get("issues", []))
            value["checks"] = checks if isinstance(checks, list) else []
            suggestions = value.get("suggested_titles", value.get("suggestions", []))
            value["suggested_titles"] = suggestions if isinstance(suggestions, list) else []
            return value
        for nested in value.values():
            found = _normalize_pre_title_payload(nested)
            if found is not None:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _normalize_pre_title_payload(nested)
            if found is not None:
                return found
    elif isinstance(value, str):
        return _extract_pre_title_response_raw(value, allow_nested_strings=False)
    return None


def _clean_pre_title_cell(text: str) -> str:
    return str(text or "").strip().strip("`*").strip()


# Literal placeholders from the checker's own OUTPUT FORMAT block. Codex sometimes
# echoes that block (its stdout and stderr are concatenated), and the parser used to
# accept the echo as real findings — producing "HIGH RISK" rows reading
# "check name / short reason" underneath an overall PASS.
PRE_TITLE_PLACEHOLDER_TOKENS = (
    "check name",
    "short reason",
    "exact risky span or blank",
    "minimal safer wording or blank",
    "exact risky span, or leave empty",
    "minimal safer wording, or leave empty",
    "full suggested title",
    "one short sentence",
    "pass or review or high risk",
)


def _is_pre_title_placeholder(value: str) -> bool:
    """True when a cell is a literal template placeholder rather than a finding."""
    v = re.sub(r"\s+", " ", _clean_pre_title_cell(value)).strip().casefold()
    if not v:
        return False
    v = v.strip("<>[]{}").strip()
    if v in PRE_TITLE_PLACEHOLDER_TOKENS:
        return True
    # An enumeration of every possible verdict is the format line, not a verdict.
    verdicts = sum(1 for token in ("pass", "review", "high risk") if token in v)
    return verdicts >= 2 and " or " in v


def _normalize_pre_title_result(value: str) -> str:
    v = _clean_pre_title_cell(value).upper().replace("_", " ").replace("-", " ")
    if "HIGH" in v and "RISK" in v:
        return "HIGH RISK"
    if "REVIEW" in v or "WARN" in v or "CAUTION" in v:
        return "REVIEW"
    if "PASS" in v or "OK" == v:
        return "PASS"
    return "REVIEW"


def _sanitize_pre_title_result(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Drop echoed template rows, unevidenced alarms, and duplicates.

    Applied to every parser path so JSON, line-protocol and markdown responses are
    held to the same contract:
      * any row or suggestion containing a literal placeholder is discarded;
      * a REVIEW/HIGH RISK row must carry a concrete reason or risky span, otherwise
        it is an alarm with no evidence behind it and is discarded;
      * duplicates are collapsed (the checker's stdout and stderr often both carry
        the answer);
      * an overall PASS shows no Same-DNA suggestions, per the checker's own contract.
    """
    if not isinstance(data, dict):
        return data

    overall = _normalize_pre_title_result(str(data.get("overall", "")))

    clean_checks: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in data.get("checks") or []:
        if not isinstance(row, dict):
            continue
        cells = {k: _clean_pre_title_cell(str(row.get(k, ""))) for k in
                 ("check", "result", "reason", "risky_span", "suggested_wording")}
        if any(_is_pre_title_placeholder(v) for v in cells.values()):
            continue
        if not cells["check"]:
            continue
        result = _normalize_pre_title_result(cells["result"]) if cells["result"] else "REVIEW"
        if result != "PASS" and not (cells["reason"] or cells["risky_span"]):
            continue
        key = (cells["check"].casefold(), result, cells["reason"].casefold())
        if key in seen:
            continue
        seen.add(key)
        cells["result"] = result
        clean_checks.append(cells)

    clean_suggestions: list[str] = []
    if overall != "PASS":
        seen_titles: set[str] = set()
        for item in data.get("suggested_titles") or []:
            value = _clean_pre_title_cell(str(item))
            if not value or _is_pre_title_placeholder(value):
                continue
            if value.casefold() in seen_titles:
                continue
            seen_titles.add(value.casefold())
            clean_suggestions.append(value)

    data["overall"] = overall
    data["checks"] = clean_checks
    data["suggested_titles"] = clean_suggestions[:3]
    return data


def _extract_pre_title_line_protocol(text: str) -> dict[str, Any] | None:
    """Parse the intentionally-simple line protocol used by the advisory checker."""
    overall = ""
    summary = ""
    checks: list[dict[str, str]] = []
    suggestions: list[str] = []

    for raw_line in (text or "").splitlines():
        line = raw_line.strip().strip("`").strip()
        if not line:
            continue
        m = re.match(r"^(?:OVERALL|STATUS|VERDICT)\s*:\s*(.+)$", line, re.I)
        if m:
            if not _is_pre_title_placeholder(m.group(1)):
                overall = _normalize_pre_title_result(m.group(1))
            continue
        m = re.match(r"^SUMMARY\s*:\s*(.+)$", line, re.I)
        if m:
            if not _is_pre_title_placeholder(m.group(1)):
                summary = _clean_pre_title_cell(m.group(1))
            continue
        if re.match(r"^CHECK\s*[|\t]", line, re.I):
            parts = [p.strip() for p in re.split(r"\s*[|\t]\s*", line)]
            # CHECK | check | result | reason | risky_span | suggested_wording
            if len(parts) >= 4:
                parts += [""] * (6 - len(parts))
                checks.append({
                    "check": _clean_pre_title_cell(parts[1]),
                    "result": _normalize_pre_title_result(parts[2]),
                    "reason": _clean_pre_title_cell(parts[3]),
                    "risky_span": _clean_pre_title_cell(parts[4]),
                    "suggested_wording": _clean_pre_title_cell(parts[5]),
                })
            continue
        m = re.match(r"^(?:SUGGESTION|SUGGESTED TITLE)\s*(?:[|:\t])\s*(.+)$", line, re.I)
        if m:
            val = _clean_pre_title_cell(m.group(1))
            if val:
                suggestions.append(val)

    if overall:
        return {
            "overall": overall,
            "summary": summary or "Title wording reviewed.",
            "checks": checks,
            "suggested_titles": suggestions[:3],
        }
    return None


def _extract_pre_title_markdown(text: str) -> dict[str, Any] | None:
    """Best-effort parser for common Codex markdown if it ignores the requested format."""
    # Find a clear verdict anywhere in headings/bold/plain text.
    m = re.search(r"(?im)^\s*(?:#+\s*)?(?:\*\*)?(?:overall|status|verdict)(?:\*\*)?\s*[:\-]\s*(?:\*\*)?\s*(HIGH[ _-]?RISK|REVIEW|PASS)\b", text or "")
    if not m:
        m = re.search(r"(?im)^\s*(?:#+\s*)?(HIGH[ _-]?RISK|REVIEW|PASS)\b", text or "")
    if not m:
        return None
    overall = _normalize_pre_title_result(m.group(1))

    summary = ""
    sm = re.search(r"(?im)^\s*(?:\*\*)?summary(?:\*\*)?\s*[:\-]\s*(.+)$", text or "")
    if sm:
        summary = _clean_pre_title_cell(sm.group(1))
    if not summary:
        # First useful prose line after the verdict, excluding headings/tables.
        for raw_line in (text or "").splitlines():
            line = raw_line.strip()
            if not line or line.startswith(("#", "|", "```")):
                continue
            if re.search(r"\b(?:overall|status|verdict)\b", line, re.I):
                continue
            if len(line) >= 12:
                summary = _clean_pre_title_cell(re.sub(r"^[-*]\s*", "", line))[:500]
                break

    suggestions: list[str] = []
    in_suggestions = False
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if re.search(r"suggest(?:ed|ions?)?\s+titles?", line, re.I):
            in_suggestions = True
            continue
        if in_suggestions:
            if line.startswith("#") and not re.search(r"suggest", line, re.I):
                break
            mm = re.match(r"^(?:[-*]|\d+[.)])\s+(.+)$", line)
            if mm:
                val = _clean_pre_title_cell(mm.group(1))
                if val:
                    suggestions.append(val)
                    if len(suggestions) >= 3:
                        break
            elif line and not line.startswith("|") and len(suggestions) > 0:
                break

    return {"overall": overall, "summary": summary or "Title wording reviewed.", "checks": [], "suggested_titles": suggestions[:3]}


def _extract_pre_title_response(raw: str, allow_nested_strings: bool = True) -> dict[str, Any] | None:
    """Extract advisory output from JSON, line protocol, JSONL/wrappers, or markdown."""
    return _sanitize_pre_title_result(_extract_pre_title_response_raw(raw, allow_nested_strings))


def _extract_pre_title_response_raw(raw: str, allow_nested_strings: bool = True) -> dict[str, Any] | None:
    text = (raw or "").strip().lstrip("\ufeff")
    if not text:
        return None
    decoder = json.JSONDecoder()

    # 1) Plain/nested JSON.
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = None
    if value is not None:
        found = _normalize_pre_title_payload(value)
        if found is not None:
            return found

    # 2) Noisy stdout containing one or more JSON values/events.
    for idx, ch in enumerate(text):
        if ch not in "{[":
            continue
        try:
            value, _ = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        found = _normalize_pre_title_payload(value)
        if found is not None:
            return found

    # 3) Stable line protocol (preferred because CLI noise cannot invalidate it).
    found = _extract_pre_title_line_protocol(text)
    if found is not None:
        return found

    # 4) JSONL / nested assistant text.
    if allow_nested_strings:
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            found = _normalize_pre_title_payload(value)
            if found is not None:
                return found

    # 5) Common markdown fallback if Codex ignores the requested wire format.
    return _extract_pre_title_markdown(text)


# Backward-compatible helper name used by existing tests/builds.
def _extract_pre_title_json(raw: str, allow_nested_strings: bool = True) -> dict[str, Any] | None:
    return _extract_pre_title_response(raw, allow_nested_strings=allow_nested_strings)


def _run_pre_title_check(title: str) -> tuple[dict[str, Any] | None, str | None]:
    """Advisory pre-project title check. Never writes files, DB rows, logs, or projects."""
    command_template = detect_codex_command()
    if not command_template:
        return None, "Codex CLI is not configured, so the advisory title check cannot run."
    prompt = f"""You are a PRE-TITLE CHECKER for a senior-health YouTube channel (audience 60+).
This happens BEFORE project creation. It is advisory only.

TITLE TO CHECK:
{title}

TASK:
Check only the title's wording/semantic promise for obvious medical/evidence risk. Do not research the web, do not create files, do not modify the title, and do not make any project/pipeline decision.
Preserve the title's audience, number hook, curiosity device, sentence skeleton, and psychology when suggesting alternatives. Change only the minimum risky wording needed.
Flag especially: cure/reverse/prevent/treat implications; universal age-wide instructions; guaranteed outcomes; unsupported precision or special timing; medication replacement; disease claims; and wording that turns a conditional nutrition/exercise association into a promised result.
Do not over-police ordinary curiosity wording. A warning means REVIEW, not automatic rejection.

OUTPUT FORMAT — use plain lines exactly, NOT JSON and NOT a markdown table. Angle brackets mark values you must replace; never output the bracketed words themselves:
OVERALL: <PASS|REVIEW|HIGH RISK>
SUMMARY: <one short sentence>
CHECK|<check name>|<PASS|REVIEW|HIGH RISK>|<short reason>|<exact risky span, or leave empty>|<minimal safer wording, or leave empty>

Use as many CHECK lines as useful, each describing a real check you performed. Never emit a CHECK line whose verdict is REVIEW or HIGH RISK without a concrete reason naming the exact wording at issue. Give exactly 3 SUGGESTION lines, formatted SUGGESTION|<full suggested title>, ONLY when OVERALL is REVIEW or HIGH RISK; for PASS give no SUGGESTION lines. Do not repeat this format block, do not output the placeholder words above, do not restate your answer twice, and output nothing before or after these lines.
"""
    try:
        template = command_template.replace("--sandbox workspace-write", "--sandbox read-only")
        if "{prompt}" not in template:
            return None, "Codex command template must include {prompt}."
        # IMPORTANT: pass the complete multi-line checker prompt through stdin.
        # On Windows, embedding a multi-line prompt in a shell command can cause
        # cmd.exe / codex.cmd to receive only the first line as the positional
        # prompt. Codex Exec supports a lone `-` positional sentinel meaning
        # "read the prompt from stdin", which preserves the title and protocol
        # exactly without creating a temporary prompt file.
        cmd = template.replace("{prompt}", "-").replace(
            "{project}",
            subprocess.list2cmdline([str(ROOT)]) if os.name == "nt" else shlex.quote(str(ROOT)),
        )
        completed = subprocess.run(
            cmd,
            cwd=ROOT,
            shell=True,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            env=os.environ.copy(),
        )
        combined = "\n".join(x for x in [(completed.stdout or "").strip(), (completed.stderr or "").strip()] if x)
        if completed.returncode != 0:
            return None, combined[-3000:] or f"Codex exited with code {completed.returncode}."
        data = _extract_pre_title_response(combined)
        if data is None:
            # Do not fail the whole user action merely because Codex decorated the answer.
            # Surface a safe advisory fallback while keeping the checker non-persistent.
            compact = re.sub(r"\s+", " ", combined).strip()
            if compact:
                return {
                    "overall": "REVIEW",
                    "summary": "Codex returned an advisory response in an unrecognized format; review the response text below.",
                    "checks": [{
                        "check": "Checker response",
                        "result": "REVIEW",
                        "reason": compact[:1200],
                        "risky_span": "",
                        "suggested_wording": "",
                    }],
                    "suggested_titles": [],
                }, None
            return None, "Pre-title checker returned an empty response. The checker did not create or save a project."
        return data, None
    except subprocess.TimeoutExpired:
        return None, "Pre-title check timed out."
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, f"Pre-title check failed: {exc}"

def _render_pre_title_result(result: dict[str, Any]) -> None:
    overall = str(result.get("overall", "REVIEW"))
    if overall == "PASS":
        st.success(f"Pre-Title Check: PASS — {result.get('summary', '')}")
    elif overall == "HIGH RISK":
        st.error(f"Pre-Title Check: HIGH RISK — {result.get('summary', '')}")
    else:
        st.warning(f"Pre-Title Check: REVIEW — {result.get('summary', '')}")
    checks = result.get("checks") or []
    if checks:
        st.dataframe(pd.DataFrame(checks), hide_index=True, width="stretch")
    suggestions = [str(x).strip() for x in (result.get("suggested_titles") or []) if str(x).strip()]
    if suggestions:
        st.markdown("**Same-DNA suggestions (advisory only):**")
        for suggestion in suggestions:
            st.code(suggestion, language="text")
    st.caption("Temporary advisory only — this result is not saved to the project, Analytics DB, or RunLogs. Creating a project still uses exactly the title currently entered above.")

def render_new_project() -> None:
    st.subheader("New Project")
    topic = st.text_input("Anchor / Outlier Title", help="Enter a candidate title. You can run the temporary Pre-Title Check before project creation. Only the title present when Create Project is clicked becomes the immutable winning title/source of truth.")
    st.markdown("### Pre-Title Check (before project creation)")
    st.caption("Checks the title only and shows advisory issues/same-DNA suggestions. It does not save anything or change the title.")
    if st.button("Check Title", disabled=not topic.strip()):
        with st.spinner("Checking title wording..."):
            result, error = _run_pre_title_check(topic.strip())
        if error:
            st.error(error)
            st.session_state.pop("pre_title_result", None)
            st.session_state.pop("pre_title_source", None)
        else:
            st.session_state["pre_title_result"] = result
            st.session_state["pre_title_source"] = topic.strip()
    if st.session_state.get("pre_title_source") == topic.strip() and st.session_state.get("pre_title_result"):
        _render_pre_title_result(st.session_state["pre_title_result"])
    elif st.session_state.get("pre_title_result"):
        st.info("Title changed since the last temporary check. Run Check Title again if you want an updated advisory review.")
    slug = slugify_topic(topic)
    st.caption(f"Folder: Projects/{slug}")
    if st.button("Create Project", type="primary", disabled=not topic.strip()):
        path = PROJECTS_DIR / slug; path.mkdir(parents=True, exist_ok=True)
        anchor = topic.strip()
        project_id = __import__("uuid").uuid4().hex
        safe_write_text(path / "project.json", json.dumps({"project_id": project_id, "topic": anchor, "anchor_title": anchor, "created_at": datetime.now().isoformat(timespec="seconds"), "version": "3.1"}, indent=2) + "\n")
        try:
            ensure_project_record(ANALYTICS_DB_PATH, path, title=anchor)
        except Exception as exc:
            st.warning(f"Project created, but Analytics DB registration could not be completed: {exc}")
        write_anchor_claim_map(path, anchor)
        defaults = load_config().get("production_defaults", {"avatar": 40, "ai_images": 30, "stock": 10, "overlays": 20})
        payload = {**defaults, "image_duration_seconds": 10, "image_platform": "Genspark Web"}
        safe_write_text(path / "production_settings.json", json.dumps(payload, indent=2) + "\n")
        st.success(f"Created {path.name}")
        st.code(command_for_stage(path, "Topic Validation"), language="text")


def render_workflow() -> None:
    st.subheader(f"V{system_version()} Workflow Control")
    project = project_selector("workflow")
    if not project:
        return
    config = load_config()
    cli_template = detect_codex_command()
    direct_enabled = bool(config.get("direct_run_enabled", True)) and bool(cli_template)
    stored_anchor = resolve_title_anchor(project)
    if stored_anchor:
        claim_map_path = project / "01a_anchor_claim_map.json"
        st.markdown("### Anchor-First Preflight")
        st.caption(f"Authoritative Winning Title: {stored_anchor}")
        st.caption(f"Claim Map: {'READY' if claim_map_path.is_file() else 'MISSING'} · 01a_anchor_claim_map.json")
    stage = st.selectbox("Stage", WORKFLOW_STAGES)
    anchor_outlier_pattern = None
    resolved_title_anchor = resolve_title_anchor(project)
    default_prompt = command_for_stage(project, stage)
    anchor_context_marker = resolved_title_anchor or ""
    prompt_context = f"{project.name}:{stage}:{anchor_context_marker}"
    prompt = sync_project_prompt_state(
        st.session_state,
        prompt_key="workflow_agent_prompt",
        context_key="workflow_agent_prompt_context",
        context_value=prompt_context,
        default_prompt=default_prompt,
    )
    lock = production_lock(project, config)
    stage_is_ready, stage_reasons = stage_ready(project, stage, config)
    stage_blocked = not stage_is_ready
    if stage == "Production Package" and stage_blocked:
        st.error("Production Lock is active. " + " ".join(lock.reasons))
    elif stage_blocked:
        st.error(f"{stage} is blocked. " + " ".join(stage_reasons))
    elif stage == "Writer Workspace":
        st.info("Writer Workspace is a manual Claude handoff stage. Use the dedicated page to download the package and upload the final script.")
    prompt = st.text_area("Agent instruction", height=230, key="workflow_agent_prompt")
    c1, c2, c3 = st.columns(3)
    c1.download_button("Download Instruction", prompt, file_name=f"{project.name}_{slugify_topic(stage)}.txt")
    run_clicked = c2.button(
        "Direct Codex Run",
        type="primary",
        disabled=not direct_enabled or stage_blocked or stage == "Writer Workspace",
    )
    if c3.button("Validate Project"):
        issues = validate_project(project, config)
        st.success("Project structure is valid.") if not issues else st.warning("\n".join(issues))
    if run_clicked:
        cleaner_ok = True
        if stage == "Production Package":
            with st.spinner("Running automatic Production Cleaner preflight..."):
                clean = clean_production_script(project, config, log_dir=RUN_LOG_DIR)
            cleaner_ok = clean.success
            if clean.success:
                st.success("Production Cleaner preflight passed.")
            else:
                st.error("Production Cleaner preflight failed. Production Package was not started.")
                for issue in clean.issues: st.write(f"- {issue}")
        if cleaner_ok:
            with st.spinner(f"Running {stage}..."):
                result = run_external_command(cli_template, prompt, project, None, None, stage=stage)
            if result.returncode == 0:
                if stage == "Production Package":
                    sanitize_csv_file(
                        project / "07_production_sheet.csv",
                        required_text_columns=("script_excerpt", "Script Text", "narration"),
                    )
                    prompt_output = project / "10_image_prompts.md"
                    if prompt_output.is_file():
                        semantic_audit = enforce_final_semantic_report(prompt_output)
                        if semantic_audit.passed:
                            st.success(f"{stage} completed. Log: {Path(result.log_path).name}")
                        else:
                            ids = ", ".join(f"IMAGE {x.image_number:03d}" for x in semantic_audit.issues)
                            st.error(f"{stage} generated diagnostic output but Semantic Coherence verification failed ({ids}). 10_image_prompts.md is NOT PRODUCTION READY.")
                    else:
                        st.success(f"{stage} completed. Log: {Path(result.log_path).name}")
                elif stage == "Thumbnail":
                    thumbnail_validation = validate_thumbnail_concepts(project)
                    if thumbnail_validation.passed:
                        st.success(f"{stage} completed and deterministic thumbnail validation passed. Log: {Path(result.log_path).name}")
                        for warning in thumbnail_validation.warnings:
                            st.warning(warning)
                    else:
                        st.error(
                            f"{stage} generated output, but deterministic thumbnail validation FAILED. "
                            "04_thumbnail_concepts.md / 11_thumbnail_prompt.md are NOT THUMBNAIL READY."
                        )
                        for issue in thumbnail_validation.issues:
                            st.write(f"- {issue}")
                        for warning in thumbnail_validation.warnings:
                            st.warning(warning)
                else:
                    st.success(f"{stage} completed. Log: {Path(result.log_path).name}")
            else:
                st.error(f"{stage} exited with code {result.returncode}.")
            st.code(result.output or "No output", language="text")
    if not direct_enabled:
        st.info("Direct Codex Run is disabled or Codex CLI is unavailable. Configure it in Config.")
    last_run = project / ".last_run.json"
    if last_run.exists():
        data = json.loads(safe_read_text(last_run) or "{}")
        st.caption(f"Last run: {data.get('finished_at', '-')} · Exit code {data.get('returncode', '-')}")


def render_writer_workspace() -> None:
    st.subheader("Writer Workspace")
    st.caption("Manual Claude writing stage between Prepare Opus Package and Narrative QA.")
    project = project_selector("writer_workspace")
    if not project:
        return
    config = load_config()
    package_path = project / "opus_writer_package.md"
    package_issues = opus_writer_package_runtime_issues(project) if package_path.is_file() else []
    package_ready = package_path.is_file() and package_path.stat().st_size > 0 and not package_issues
    validation = validate_final_script(project, config)

    c1, c2, c3 = st.columns(3)
    c1.metric("Opus Package", "READY" if package_ready else "MISSING")
    c2.metric("Final Script", "VALID" if validation.valid else ("INVALID" if validation.exists else "MISSING"))
    c3.metric("Narrative QA", "UNLOCKED" if validation.valid else "BLOCKED")

    if package_ready:
        package_text = safe_read_text(package_path)
        try:
            active_rules_block = render_active_channel_rules_markdown(ANALYTICS_DB_PATH)
        except Exception:
            active_rules_block = ""
        if active_rules_block and "_No ACTIVE channel script rules yet._" not in active_rules_block:
            marker = "# ACTIVE CHANNEL SCRIPT RULES"
            if marker not in package_text:
                package_text = (
                    package_text.rstrip()
                    + "\n\n---\n\n"
                    + active_rules_block.strip()
                    + "\n"
                )
        st.download_button(
            "Download Opus Package",
            package_text.encode("utf-8"),
            file_name=f"{project.name}_opus_writer_package.md",
            mime="text/markdown",
        )
    else:
        if package_issues:
            st.error("The existing Opus package is blocked by the advisory-only runtime contract. Regenerate Prepare Opus Package.")
            for issue in package_issues:
                st.write(f"- {issue}")
        else:
            st.warning("Prepare Opus Package must be completed first. Expected opus_writer_package.md.")

    try:
        writer_active_rules = active_channel_script_rules(ANALYTICS_DB_PATH)
        if writer_active_rules.empty:
            st.caption("Active Channel Script Rules: none yet.")
        else:
            st.success(
                f"Active Channel Script Rules: {len(writer_active_rules)} rule(s) auto-injected into the downloaded Opus package."
            )
            with st.expander("Show auto-applied channel rules"):
                for _, rr in writer_active_rules.iterrows():
                    st.write(f"• **{rr['script_pattern']}** — {rr['rule_text']}")
    except Exception:
        pass

    st.markdown("### Manual instructions for Claude")
    st.info("1. Download the Opus package. 2. Upload/paste it into Claude. 3. Ask Claude to write the complete script while preserving the package rules and Markdown headings. 4. Export the result as .md or .txt. 5. Upload it below; the app will save it safely as 06_final_script.md.")

    render_runtime_authority_notice(config)
    target = f"Target: {validation.target_words_min:,}–{validation.target_words_max:,} words · {validation.target_runtime_min:g}–{validation.target_runtime_max:g} minutes at {canonical_runtime(config).wpm} WPM."
    st.caption(target)
    uploaded = st.file_uploader("Upload completed script", type=["md", "txt"], accept_multiple_files=False, key=f"writer_upload_{project.name}")
    existing = (project / "06_final_script.md").exists()
    if existing:
        st.warning("An existing 06_final_script.md will be backed up automatically before replacement.")
    confirm = st.checkbox("I confirm replacement of the existing script", value=not existing, disabled=not existing, key=f"writer_confirm_{project.name}")
    if st.button("Save as 06_final_script.md", type="primary", disabled=uploaded is None or (existing and not confirm)):
        result = save_uploaded_script(project, uploaded.name, uploaded.getvalue(), config, create_backup=True, log_dir=RUN_LOG_DIR)
        if result.success:
            st.success(result.message)
        else:
            st.error(result.message)
        if result.backup_path:
            st.info(f"Backup created: {Path(result.backup_path).relative_to(project)}")
        validation = result.validation

    validation = validate_final_script(project, config)
    st.markdown("### Script validation")
    m1, m2, m3 = st.columns(3)
    m1.metric("Word count", f"{validation.word_count:,}")
    m2.metric("Estimated runtime", f"{validation.runtime_minutes:g} min")
    comparison = "IN RANGE" if validation.target_words_min <= validation.word_count <= validation.target_words_max else "OUTSIDE TARGET"
    m3.metric("Target comparison", comparison)
    if validation.issues:
        for issue in validation.issues:
            st.error(issue)
    elif validation.valid:
        st.success("Required headings and basic content checks passed. Narrative QA is unlocked.")
    if validation.exists:
        st.markdown("### Script Quality Metrics")
        metrics = script_quality_metrics(safe_read_text(project / "06_final_script.md"), config)
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("Avg sentence", f"{metrics.average_sentence_length:g} words", help=f"Target: {metrics.target_ranges['Average sentence length']}")
        q2.metric("Avg paragraph", f"{metrics.average_paragraph_length:g} words", help=f"Target: {metrics.target_ranges['Average paragraph length']}")
        q3.metric("Contractions", f"{metrics.contractions_percent:g}%", help=f"Target: {metrics.target_ranges['Contractions']}")
        q4.metric("Read-aloud score", f"{metrics.read_aloud_score:g}/100", help=f"Target: {metrics.target_ranges['Read-aloud score']}")
        q5, q6, q7, q8 = st.columns(4)
        q5.metric("Total runtime", f"{metrics.total_runtime_minutes:g} min")
        q6.metric("Estimated video duration", f"{metrics.estimated_video_duration_minutes:g} min")
        q7.metric("ElevenLabs pauses", metrics.estimated_elevenlabs_pauses, help=f"Target: {metrics.target_ranges['Breathing rhythm']}")
        q8.metric("Reading ease", metrics.reading_difficulty, help=f"Target: {metrics.target_ranges['Reading ease']}")

        st.markdown("#### Read-aloud Score Breakdown")
        breakdown_rows=[{"Component": name, "Score": score, "Target": "75–100"} for name, score in metrics.read_aloud_breakdown.items()]
        st.dataframe(pd.DataFrame(breakdown_rows), hide_index=True, width="stretch")

        st.markdown("#### Contraction Analysis")
        st.caption(f"{metrics.contraction_opportunity_count} possible conversational contraction opportunities found. Suggestions only; the script is not modified.")
        if metrics.contraction_opportunities:
            st.dataframe(pd.DataFrame([{"Current": item['source'], "Suggestion": item['replacement'], "Opportunities": item['count']} for item in metrics.contraction_opportunities]), hide_index=True, width="stretch")
        else:
            st.success("No common uncontracted phrases were detected.")

        st.markdown("#### Repeated Sentence Opening Inspector")
        if metrics.repeated_opening_details:
            badge_colors={"Good":"#1f9d55","Moderate":"#d69e2e","High":"#d64545"}
            for item in metrics.repeated_opening_details:
                color=badge_colors[item['level']]
                title=f"{item['opening']} ({item['count']})"
                st.markdown(f"<span style='background:{color};color:white;padding:3px 9px;border-radius:12px;font-weight:600'>{item['level']}</span> &nbsp; **{title}**", unsafe_allow_html=True)
                with st.expander(f"Show {item['count']} locations", expanded=False):
                    st.dataframe(pd.DataFrame([{"Section": occurrence['section'], "Sentence": occurrence['sentence'], "Sentence in section": occurrence['section_sentence']} for occurrence in item['occurrences']]), hide_index=True, width="stretch")
        else:
            st.success("Good: no sentence opening appears three or more times.")

        st.markdown("#### Runtime by Section")
        if metrics.section_runtime:
            runtime_rows=[]
            for name,value in metrics.section_runtime.items():
                runtime_rows.append({"Section":name,"Runtime (min)":value,"Comparison":"SIGNIFICANTLY LONGER" if name in metrics.long_sections else "Normal"})
            st.dataframe(pd.DataFrame(runtime_rows), hide_index=True, width="stretch")
            if metrics.long_sections:
                st.warning("Longer than average: " + ", ".join(metrics.long_sections))
        r1,r2=st.columns(2)
        r1.metric("Rhetorical questions", metrics.rhetorical_question_count)
        r2.metric("Narration WPM", metrics.estimated_narration_wpm)
        st.markdown("### Uploaded script preview")
        st.text_area("06_final_script.md", validation.preview, height=520, disabled=True, key=f"writer_preview_{project.name}")


def _retention_revision_applied(project: Path) -> bool:
    """True once the analyzed final script has been revised after the one retention pass."""
    script_path = project / "06_final_script.md"
    report_path = project / "retention_structure_analysis.md"
    if not script_path.is_file() or not report_path.is_file():
        return False
    try:
        return script_path.stat().st_mtime > report_path.stat().st_mtime
    except OSError:
        return False


def render_retention_structure_analysis() -> None:
    st.subheader("Retention Structure Analysis")
    st.caption("Structural retention editor only: order and pacing. It does not judge medical correctness or change the winning title.")
    project = project_selector("retention_structure_analysis")
    if not project:
        return
    config = load_config()
    validation = validate_final_script(project, config)
    report_path = project / "retention_structure_analysis.md"
    report = get_gate_status(project, "Retention Structure Analysis", config, filename="retention_structure_analysis.md")
    retention_complete = _retention_revision_applied(project)

    c1, c2, c3 = st.columns(3)
    c1.metric("Final Script", "VALID" if validation.valid else "BLOCKED")
    c2.metric("Analysis", "RETENTION_COMPLETE" if retention_complete else report.status)
    c3.metric("Output", "READY" if report_path.is_file() else "MISSING")

    can_start, blocked_reasons = retention_structure_ready(project, config)
    if not can_start:
        st.warning("Retention Structure Analysis cannot run yet: " + " ".join(blocked_reasons))

    if retention_complete:
        st.success("Retention Complete — Continue to Narrative QA")
        st.info("The analyzed script has been revised after its one retention pass. Automatic re-analysis is locked to prevent reorder ping-pong.")
    elif report_path.is_file():
        st.info("Retention analysis has already run for this script version. Apply its Script Chat Revision Prompt and upload/save the revised 06_final_script.md. Do not run Retention Analysis again.")

    default_prompt = command_for_stage(project, "Retention Structure Analysis")
    reset_prompt = st.button("Reset Retention Prompt", key=f"reset_retention_prompt_{project.name}")
    prompt = sync_project_prompt_state(
        st.session_state,
        prompt_key="retention_structure_prompt",
        context_key="retention_structure_prompt_project",
        context_value=project.name,
        default_prompt=default_prompt,
        force_reset=reset_prompt,
    )
    prompt = st.text_area("Retention Structure Analysis instruction", height=240, key="retention_structure_prompt")

    cli_template = detect_codex_command()
    can_run = bool(cli_template) and can_start and not report_path.is_file()
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("Download Retention Instruction", prompt, file_name=f"{project.name}_retention-structure-analysis.txt")
    with c2:
        if st.button("Run Retention Structure Analyzer", type="primary", disabled=not can_run):
            with st.spinner("Analyzing script structure and pacing..."):
                result = run_external_command(cli_template, prompt, project)
            if result.returncode == 0:
                st.success("Retention Structure Analyzer completed.")
                st.rerun()
            else:
                st.error(f"Retention Structure Analyzer exited with code {result.returncode}.")
                st.code(result.output or "No output", language="text")

    if report_path.is_file():
        st.markdown("### Latest Retention Structure Analysis")
        report_text = safe_read_text(report_path)
        st.markdown(report_text)
        st.download_button("Download retention_structure_analysis.md", report_text, file_name="retention_structure_analysis.md", mime="text/markdown")
        if not retention_complete:
            st.info("Apply the report's Script Chat Revision Prompt to the script, then upload/save the revised 06_final_script.md. This is the only retention pass; after revision, continue to Narrative QA without re-running Retention Analysis.")
    elif not cli_template:
        st.info("Codex CLI was not found. Install/login to Codex CLI, or set codex_cli_command in config.json.")


def record_narrative_qa_runtime_routing(project: Path, config: dict[str, Any]) -> None:
    """Charge the redevelopment budget when a QA report routes back for runtime."""
    report = project / "14_narrative_qa.md"
    if not report.is_file():
        return
    claim = parse_runtime_shortfall(report.read_text(encoding="utf-8", errors="replace"))
    if claim is None or claim.cause not in RUNTIME_ROUTING_CAUSES:
        return
    script = project / "06_final_script.md"
    if not script.is_file():
        return
    record_runtime_redevelopment(project, script.read_text(encoding="utf-8", errors="replace"))
    if runtime_redevelopment_budget_spent(project, config):
        st.error(
            "Runtime redevelopment budget is spent for this project. Another Writer "
            "expansion cycle is not permitted — treat this as "
            "SOURCE_POOL_EFFECTIVELY_EXHAUSTED and decide the runtime/research "
            "configuration instead."
        )


def render_narrative_qa() -> None:
    st.subheader("Narrative QA Agent")
    if st.session_state.get("gate_refresh_notice"):
        st.success(st.session_state.pop("gate_refresh_notice"))
    st.caption("Checks storytelling, pacing, repetition, transitions, hook payoff, tone, CTA placement, and retention. Medical claims are checked separately in Medical Gate 2.")
    project = project_selector("narrative_qa")
    if not project:
        return

    outline_ready = (project / "05_script_outline.md").exists()
    validation = validate_final_script(project, load_config())
    script_ready = validation.valid
    narrative_gate = get_gate_status(project, "Narrative QA", load_config())
    output_ready = narrative_gate.exists
    record_narrative_qa_runtime_routing(project, load_config())

    c1, c2, c3 = st.columns(3)
    c1.metric("Script Outline", "READY" if outline_ready else "MISSING")
    c2.metric("Writer Workspace", "VALID" if script_ready else "BLOCKED")
    c3.metric("Narrative QA", narrative_gate.status)

    can_start, blocked_reasons = narrative_qa_ready(project, load_config())
    if not can_start:
        st.warning("Narrative QA cannot run yet: " + " ".join(blocked_reasons))

    default_prompt = command_for_stage(project, "Narrative QA")
    reset_prompt = st.button(
        "Reset Narrative Prompt",
        key=f"reset_narrative_prompt_{project.name}",
        help="Restore the default Narrative QA instruction for the currently selected project.",
    )
    prompt = sync_project_prompt_state(
        st.session_state,
        prompt_key="narrative_qa_prompt",
        context_key="narrative_prompt_project",
        context_value=project.name,
        default_prompt=default_prompt,
        force_reset=reset_prompt,
    )
    prompt = st.text_area("Narrative QA instruction", height=220, key="narrative_qa_prompt")

    cli_template = detect_codex_command()
    can_run = bool(cli_template) and can_start
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("Download Narrative QA Instruction", prompt, file_name=f"{project.name}_narrative-qa.txt")
    with c2:
        if st.button("Run Narrative QA Agent", type="primary", disabled=not can_run):
            with st.spinner("Running Narrative QA Agent..."):
                result = run_external_command(cli_template, prompt, project)
            code, output = result.returncode, result.output
            if code == 0:
                st.session_state["gate_refresh_notice"] = "Narrative QA Agent completed. Gate status refreshed from the latest report."
                st.rerun()
            else:
                st.error(f"Narrative QA Agent exited with code {code}.")
                st.code(output or "No output", language="text")

    if output_ready:
        st.markdown("### Latest Narrative QA Report")
        report_text = safe_read_text(project / "14_narrative_qa.md")
        st.markdown(report_text)
        if "Current Text:" in report_text and "Replace With:" in report_text:
            if st.button("Apply Narrative Revisions", type="primary"):
                result = apply_revision_patch(project, "14_narrative_qa.md", log_dir=RUN_LOG_DIR)
                (st.success if result.success else st.error)(result.message)
                if result.backup_path: st.info(f"Backup: {Path(result.backup_path).relative_to(project)}")
    elif not cli_template:
        st.info("Codex CLI was not found. Install/login to Codex CLI, or set codex_cli_command in config.json.")

def render_medical_gate_2() -> None:
    st.subheader("Medical Gate 2")
    if st.session_state.get("gate_refresh_notice"):
        st.success(st.session_state.pop("gate_refresh_notice"))
    project = project_selector("medical_gate_2")
    if not project:
        return
    config = load_config()
    report = get_gate_status(project, "Medical Gate 2", config)
    c1, c2, c3 = st.columns(3)
    c1.metric("Final Script", "READY" if (project / "06_final_script.md").exists() else "MISSING")
    c2.metric("Evidence", "READY" if (project / "02_research_sheet.md").exists() else "MISSING")
    c3.metric("Gate Status", report.status)
    default_prompt = command_for_stage(project, "Medical Gate 2")
    prompt = sync_project_prompt_state(
        st.session_state,
        prompt_key="medical_gate_2_prompt",
        context_key="medical_gate_2_prompt_project",
        context_value=project.name,
        default_prompt=default_prompt,
    )
    prompt = st.text_area("Medical Gate 2 instruction", height=220, key="medical_gate_2_prompt")
    cli = detect_codex_command()
    ready, reasons = stage_ready(project, "Medical Gate 2", config)
    if not ready: st.warning("Medical Gate 2 is blocked. " + " ".join(reasons))
    can_run = bool(cli) and ready and (project / "02_research_sheet.md").exists()
    if st.button("Run Medical Gate 2", type="primary", disabled=not can_run):
        with st.spinner("Running Medical Gate 2..."):
            result = run_external_command(cli, prompt, project)
        if result.returncode == 0:
            st.session_state["gate_refresh_notice"] = "Medical Gate 2 completed. Gate status refreshed from the latest report."
            st.rerun()
        st.error(f"Medical Gate 2 exit code: {result.returncode}")
        st.code(result.output or "No output")
    path = project / config.get("medical_gate_2_output", "15_medical_gate_2.md")
    if path.exists():
        st.markdown("### Latest Report")
        report_text = safe_read_text(path)
        st.markdown(report_text)
        if "Current Text:" in report_text and "Replace With:" in report_text:
            if st.button("Apply Medical Revisions", type="primary"):
                result = apply_revision_patch(project, path.name, log_dir=RUN_LOG_DIR)
                (st.success if result.success else st.error)(result.message)
                if result.backup_path: st.info(f"Backup: {Path(result.backup_path).relative_to(project)}")


def render_speech_optimizer() -> None:
    st.subheader("Speech Optimizer")
    if st.session_state.get("gate_refresh_notice"):
        st.success(st.session_state.pop("gate_refresh_notice"))
    project = project_selector("speech_optimizer")
    if not project:
        return
    config = load_config()
    ready, reasons = stage_ready(project, "Speech Optimizer", config)
    blocked = not ready
    if blocked:
        st.warning("Speech Optimizer requires a non-empty 06_final_script.md. " + " ".join(reasons))
    default_prompt = command_for_stage(project, "Speech Optimizer")
    prompt = sync_project_prompt_state(
        st.session_state,
        prompt_key="speech_optimizer_prompt",
        context_key="speech_optimizer_prompt_project",
        context_value=project.name,
        default_prompt=default_prompt,
    )
    prompt = st.text_area("Speech Optimizer instruction", height=220, key="speech_optimizer_prompt")
    cli = detect_codex_command()
    if st.button("Run Speech Optimizer", type="primary", disabled=blocked or not cli):
        with st.spinner("Optimizing speech delivery..."):
            result = run_external_command(cli, prompt, project)
        (st.success if result.returncode == 0 else st.error)(f"Speech Optimizer exit code: {result.returncode}")
        st.code(result.output or "No output")
    c1, c2 = st.columns(2)
    c1.metric("Voice Script", "READY" if (project / "06a_voice_script.md").exists() else "MISSING")
    c2.metric("Voice Checklist", "READY" if (project / "06b_voice_checklist.md").exists() else "MISSING")


def render_qa_dashboard() -> None:
    st.subheader("Advanced QA Dashboard")
    project = project_selector("qa_dashboard")
    if not project: return
    config = load_config()
    rows = qa_dashboard(project, config)
    badge_colors={"PASS":"#1f9d55","PASS WITH REVISIONS":"#d69e2e","PASS WITH SUGGESTIONS":"#d69e2e","FAIL":"#d64545","MISSING":"#6b7280","UNKNOWN":"#6b7280"}
    selected_report=None
    for index,row in enumerate(rows):
        c1,c2,c3,c4,c5=st.columns([1.5,1.4,.7,1.6,1.2])
        c1.markdown(f"**{row['Stage']}**")
        color=badge_colors.get(row['Status'],"#6b7280")
        c2.markdown(f"<span style='background:{color};color:white;padding:4px 10px;border-radius:12px;font-weight:700'>{row['Status']}</span>",unsafe_allow_html=True)
        c3.metric("Issues",row['Issues'])
        c4.caption(f"Last run: {row['Last Run']} · Report: {row['Report']}")
        if c5.button("Open report",key=f"qa_open_{index}_{project.name}"):
            selected_report=row['Report']
        st.divider()
    report_options=[row['Report'] for row in rows]
    if selected_report:
        st.session_state[f"qa_selected_report_{project.name}"]=selected_report
    current=st.session_state.get(f"qa_selected_report_{project.name}",report_options[0])
    if current not in report_options: current=report_options[0]
    chosen=st.selectbox("Report viewer",report_options,index=report_options.index(current),key=f"qa_report_select_{project.name}")
    st.session_state[f"qa_selected_report_{project.name}"]=chosen
    path=project/chosen
    if path.exists():
        st.markdown(f"### {chosen}")
        st.markdown(safe_read_text(path))
    else: st.info(f"{chosen} is not available yet.")

def render_production_lock() -> None:
    st.subheader("Production Lock")
    selected_project = project_selector("production_lock")
    if not selected_project:
        return
    project = sync_project_validation_context(
        st.session_state,
        context_key="production_lock_selected_project",
        selected_project=selected_project,
        invalidate_keys=("production_lock_rows", "production_lock_reasons"),
    )
    config = load_config()
    prerequisites_ok, prerequisite_reasons = production_cleaner_prerequisites(project, config)
    cleaner_result = ensure_production_cleaner(project, config, log_dir=RUN_LOG_DIR)
    if cleaner_result is not None:
        if cleaner_result.success:
            st.success("Production Cleaner ran automatically and passed.")
        else:
            st.error("Production Cleaner ran automatically and failed.")
            for issue in cleaner_result.issues: st.write(f"- {issue}")
    lock = production_lock(project, config)
    if lock.locked:
        st.error("Production is LOCKED.")
    else:
        st.success("READY FOR PRODUCTION")
    rows = [{"Check": c.name, "Status": c.status, "File": c.file, "Reason": c.reason} for c in lock.checks]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", key=f"production_lock_checks_{project.name}")
    if lock.reasons:
        st.markdown("### Blocking reasons")
        for reason in lock.reasons:
            st.write(f"- {reason}")
    if prerequisites_ok:
        label = "Run Production Cleaner Again" if production_cleaner_is_current(project, config) else "Run Production Cleaner"
        if st.button(label, type="primary", key=f"production_lock_cleaner_{project.name}"):
            clean=ensure_production_cleaner(project,config,log_dir=RUN_LOG_DIR,force=True)
            if clean and clean.success: st.success("Production Cleaner: PASS")
            elif clean:
                st.error("Production Cleaner: FAIL")
                for issue in clean.issues: st.write(f"- {issue}")
            st.rerun()
    else:
        st.info("Production Cleaner is waiting for prerequisites.")
        for reason in prerequisite_reasons: st.write(f"- {reason}")


def render_production() -> None:
    st.subheader("Production Mix")
    project = project_selector("production")
    if not project:
        return
    config = load_config()

    # production_lock() intentionally gates only on 06a_voice_script.md, because that
    # file can only be produced by the Speech Optimizer, which itself requires both
    # editorial gates at PASS. A hand-written or externally copied voice script would
    # bypass that chain silently, so surface the real gate status here.
    gate_warnings = [
        f"{name}: {get_gate_status(project, name, config).status}"
        for name in ("Narrative QA", "Medical Gate 2")
        if get_gate_status(project, name, config).status != "PASS"
    ]
    if gate_warnings:
        st.error(
            "Editorial/medical gates are not at PASS for this project — "
            + "; ".join(gate_warnings)
            + ". If 06a_voice_script.md was created outside the Speech Optimizer, this "
            "project has not cleared Narrative QA and Medical Gate 2. Resolve the gates "
            "before publishing."
        )

    st.markdown("### Production Cleaner")
    prerequisites_ok, prerequisite_reasons = production_cleaner_prerequisites(project, config)
    if prerequisites_ok:
        if not production_cleaner_is_current(project, config):
            clean = ensure_production_cleaner(project, config, log_dir=RUN_LOG_DIR)
            if clean and clean.success:
                st.success("Production Cleaner: PASS")
            elif clean:
                st.error("Production Cleaner: FAIL")
                for issue in clean.issues:
                    st.write(f"- {issue}")
        if st.button("Run Production Cleaner Again", type="primary", key=f"production_cleaner_again_{project.name}"):
            clean = ensure_production_cleaner(project, config, log_dir=RUN_LOG_DIR, force=True)
            if clean and clean.success:
                st.success("Production Cleaner: PASS")
            elif clean:
                st.error("Production Cleaner: FAIL")
                for issue in clean.issues:
                    st.write(f"- {issue}")
            st.rerun()
    else:
        st.info("Production Cleaner cannot run until prerequisites pass.")
        for reason in prerequisite_reasons:
            st.write(f"- {reason}")

    cleaner_report = project / "production_clean_report.md"
    if cleaner_report.exists():
        st.markdown(safe_read_text(cleaner_report))

    lock = production_lock(project, config)
    if lock.locked:
        st.error("Production is locked. Complete every Production Lock 2.0 checklist item first.")
        for reason in lock.reasons:
            st.write(f"- {reason}")
    else:
        st.success("READY FOR PRODUCTION")

    settings_path = project / "production_settings.json"
    defaults = {"avatar": 40, "ai_images": 30, "stock": 10, "overlays": 20, "image_duration_seconds": 10, "image_platform": "Genspark Web"}
    try:
        settings = {**defaults, **json.loads(safe_read_text(settings_path) or "{}")}
    except json.JSONDecodeError:
        settings = defaults

    c1, c2, c3, c4 = st.columns(4)
    avatar = c1.number_input("Avatar %", 0, 100, int(settings["avatar"]))
    ai_images = c2.number_input("AI Images %", 0, 100, int(settings["ai_images"]))
    stock = c3.number_input("Stock %", 0, 100, int(settings["stock"]))
    overlays = c4.number_input("Overlays %", 0, 100, int(settings["overlays"]))
    total = avatar + ai_images + stock + overlays
    mix_valid, mix_reason = validate_production_mix(avatar, ai_images, stock, overlays)
    st.metric("Total", f"{total}%")

    duration = st.number_input("AI image display duration (seconds)", 6, 20, int(settings["image_duration_seconds"]))
    options = ["Genspark Web", "Midjourney", "ChatGPT", "Other"]
    current_platform = settings.get("image_platform", "Genspark Web")
    platform = st.selectbox("Image platform", options, index=options.index(current_platform) if current_platform in options else 0)

    voice_script = safe_read_text(project / "06a_voice_script.md")
    if voice_script:
        minutes = count_words(voice_script) / max(1, canonical_runtime(config).wpm)
        estimated_images = round((minutes * 60 * ai_images / 100) / max(1, duration))
        st.info(f"Estimated runtime: {minutes:.1f} minutes · Estimated AI images: approximately {estimated_images}")
    else:
        st.info("Runtime estimate will appear when 06a_voice_script.md is available.")

    payload = {
        "avatar": avatar, "ai_images": ai_images, "stock": stock, "overlays": overlays,
        "image_duration_seconds": duration, "image_platform": platform,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if st.button("Save Production Mix", disabled=not mix_valid):
        if safe_write_text(settings_path, json.dumps(payload, indent=2) + "\n"):
            st.success("Production mix saved.")
    if not mix_valid:
        st.warning(mix_reason)

    cli_template = detect_codex_command()
    direct_enabled = bool(config.get("direct_run_enabled", True)) and bool(cli_template)
    generation_reasons = []
    if lock.locked:
        generation_reasons.append("Production Lock is not READY.")
    if not mix_valid:
        generation_reasons.append(mix_reason)
    if not direct_enabled:
        generation_reasons.append("Codex CLI is unavailable or Direct Codex Run is disabled in configuration.")

    st.markdown("### Generate Production Outputs")
    generate_disabled = bool(generation_reasons)
    if generation_reasons:
        for reason in generation_reasons:
            st.caption(f"• {reason}")

    if st.button("Generate Production Plan", type="primary", disabled=generate_disabled, key=f"generate_production_{project.name}"):
        if not safe_write_text(settings_path, json.dumps(payload, indent=2) + "\n"):
            st.error("Production generation was not started because production settings could not be saved.")
        else:
            try:
                clear_stale_production_outputs(project)
            except RuntimeError as exc:
                st.error(str(exc))
                result = None
            else:
                prompt = command_for_stage(project, "Production Package")
                try:
                    with st.spinner("Generating production outputs..."):
                        result = run_external_command(cli_template, prompt, project)
                except Exception as exc:
                    st.error(f"Production generation could not start: {type(exc).__name__}. Check the Codex CLI configuration and run log.")
                    result = None
            if result is None:
                pass
            else:
                outputs = production_outputs(project)
                source_ok = False
                source_issues: list[str] = []
                if result.returncode == 0 and (project / "07_production_sheet.csv").is_file():
                    contract_ok, contract_issues = normalize_production_sheet(project / "07_production_sheet.csv")
                    if contract_ok:
                        sanitize_csv_file(
                            project / "07_production_sheet.csv",
                            required_text_columns=("script_excerpt",),
                        )
                        source_ok, source_issues = validate_production_sheet_against_voice(project)
                        segmentation_issues = production_sheet_segmentation_issues(project)
                        if segmentation_issues:
                            source_ok = False
                            source_issues = ["SCENE_SEGMENTATION_QA_FAILED"] + segmentation_issues
                    else:
                        source_ok = False
                        source_issues = list(contract_issues)
                semantic_audit = None
                prompt_output = project / "10_image_prompts.md"
                if result.returncode == 0 and prompt_output.is_file():
                    semantic_audit = enforce_final_semantic_report(prompt_output)
                if result.returncode == 0 and all(outputs.values()) and source_ok and (semantic_audit is None or semantic_audit.passed):
                    st.success("Production generation completed successfully.")
                elif result.returncode == 0 and not source_ok:
                    if source_issues and source_issues[0] == "SCENE_SEGMENTATION_QA_FAILED":
                        st.error("Production output rejected: scene segmentation/timing QA failed. The script source itself still matches 06a_voice_script.md.")
                        display_issues = source_issues[1:]
                    else:
                        st.error("Production output rejected: 07_production_sheet.csv failed the canonical Production/source contract.")
                        display_issues = source_issues
                    for issue in display_issues[:12]:
                        st.caption(f"• {issue}")
                elif result.returncode == 0 and semantic_audit is not None and not semantic_audit.passed:
                    ids = ", ".join(f"IMAGE {x.image_number:03d}" for x in semantic_audit.issues)
                    st.error("Production outputs were generated, but final Semantic Coherence verification failed: " + ids + ". 10_image_prompts.md is NOT PRODUCTION READY.")
                elif result.returncode == 0:
                    missing = [name for name, exists in outputs.items() if not exists]
                    st.warning("Production command completed, but expected output files are missing: " + ", ".join(missing))
                else:
                    st.error(f"Production generation failed with exit code {result.returncode}. Review log: {Path(result.log_path).name}")
                st.rerun()

    outputs = production_outputs(project)
    if any(outputs.values()):
        st.markdown("### Production Outputs")
        for filename, exists in outputs.items():
            if exists:
                path = project / filename
                st.success(f"Generated: {filename}")
                data = path.read_bytes()
                mime = "text/csv" if path.suffix.lower() == ".csv" else "text/markdown"
                st.download_button(f"Download {filename}", data, file_name=filename, mime=mime, key=f"download_{project.name}_{filename}")
            else:
                st.info(f"Pending: {filename}")

    render_avatar_timing_sync(project, config, lock_ready=not lock.locked)


def render_avatar_timing_sync(project: Path, config: dict[str, Any], lock_ready: bool) -> None:
    st.markdown("---")
    st.markdown("## Avatar Timing Sync")
    st.caption("Uses actual avatar speech timing after Production Lock. Approved narration files are read-only.")

    model_settings = transcription_settings(config)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Configured Model", model_settings["configured_model"])
    m2.metric("Effective Model", model_settings["effective_model"])
    m3.metric("Timestamp Mode", model_settings["timestamp_mode"])
    m4.metric("Word Timing", "Yes" if model_settings["word_timing_available"] else "No")
    st.caption(f"Model source: {model_settings['model_source']} · Response format: {model_settings['response_format']}")

    state_key = f"avatar_folder_{project.name}"
    default_folder = str((project / "avatars").resolve())
    folder_value = st.text_input("Avatar Folder", value=st.session_state.get(state_key, default_folder), key=f"avatar_folder_input_{project.name}")
    avatar_folder = Path(folder_value).expanduser()
    if not avatar_folder.is_absolute():
        avatar_folder = (project / avatar_folder).resolve()

    if st.button("Select Avatar Folder", disabled=not lock_ready, key=f"select_avatar_folder_{project.name}"):
        st.session_state[state_key] = str(avatar_folder)
        if avatar_folder.is_dir():
            st.success(f"Avatar folder selected: {avatar_folder}")
        else:
            st.error("The selected avatar folder does not exist.")

    discovery = discover_avatar_chunks(avatar_folder) if avatar_folder.is_dir() else None
    scenes = load_production_scenes(project / "07_production_sheet.csv")
    production_source_ok = True
    production_source_issues: list[str] = []
    if scenes:
        production_source_ok, production_source_issues = validate_production_sheet_against_voice(project)
        if not production_source_ok:
            scenes = []
            st.warning("07_production_sheet.csv does not match the current 06a_voice_script.md. Regenerate Production Plan before avatar timing.")
            for issue in production_source_issues[:8]:
                st.caption(f"• {issue}")
        else:
            segmentation_issues = production_sheet_segmentation_issues(project)
            if segmentation_issues:
                st.warning("Production sheet narration matches 06a_voice_script.md, but scene segmentation/timing has QA warnings. Avatar timing may continue because real transcript timing will replace provisional scene timing.")
                for issue in segmentation_issues[:6]:
                    st.caption(f"• {issue}")
    sequence = chunk_sequence_info(discovery)
    chunks_found = sequence.detected_count
    transcript_dir = project / "avatar_transcripts"
    inventory = transcript_inventory(discovery.chunks, transcript_dir, config) if discovery else {"current": 0, "total_duration": 0.0}
    timeline_path = project / "08_actual_timeline.csv"
    manifest_path = project / "avatar_timing_manifest.json"
    report_path = project / "avatar_alignment_report.md"

    st.caption(f"Transcript save folder: {transcript_dir}")
    st.caption(f"Timeline save folder: {project}")

    alignment_score = None
    timeline_status = "NOT GENERATED"
    if manifest_path.is_file():
        try:
            manifest = json.loads(safe_read_text(manifest_path) or "{}")
            alignment_score = float(manifest.get("alignment_score", 0.0))
            timeline_status = str(manifest.get("timeline_status", "UNKNOWN"))
        except (json.JSONDecodeError, TypeError, ValueError):
            timeline_status = "INVALID MANIFEST"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Detected Chunks", chunks_found)
    c2.metric("First Chunk", sequence.first_chunk or "None")
    c3.metric("Last Chunk", sequence.last_chunk or "None")
    c4.metric("Expected Sequential Chunks", sequence.expected_count)
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Missing Chunk Numbers", ", ".join(map(str, sequence.missing_numbers)) if sequence.missing_numbers else "None")
    d2.metric("Total Avatar Duration", f"{inventory['total_duration'] / 60:.2f} min" if inventory["total_duration"] else "Pending")
    d3.metric("Total Production Scenes", len(scenes))
    d4.metric("Transcribed Chunks", f"{inventory['current']}/{chunks_found}" if chunks_found else "0")
    e1, e2, e3 = st.columns(3)
    e1.metric("Reused Cached Chunks", inventory["current"])
    e2.metric("Alignment Score", f"{alignment_score:.1f}%" if alignment_score is not None else "Pending")
    e3.metric("Timeline Status", timeline_status)

    blockers = avatar_sync_blockers(lock_ready, avatar_folder, scenes, discovery)
    if discovery:
        if discovery.unsupported:
            st.warning("Unsupported files: " + ", ".join(discovery.unsupported))
        if discovery.duplicates:
            st.warning("Duplicate/alternative chunks detected: " + " | ".join(discovery.duplicates))

    for reason in blockers:
        st.caption(f"• {reason}")

    error_key = f"avatar_transcription_error_{project.name}"
    if discovery and discovery.chunks:
        rows = preflight_avatar_chunks(discovery.chunks, transcript_dir, config)
        st.dataframe(
            pd.DataFrame([{
                "Chunk": row["chunk"], "Size MB": row["size_mb"],
                "Status": row["status"], "Action": row["action"],
            } for row in rows]),
            hide_index=True, use_container_width=True,
        )

    saved_error = st.session_state.get(error_key)
    if saved_error:
        st.error(f"Avatar transcription failed on {saved_error.get('failed_chunk', 'unknown chunk')}: {saved_error.get('exception_class')}: {saved_error.get('message')}")
        st.write({
            "Failed chunk filename": saved_error.get("failed_chunk"),
            "Exception class": saved_error.get("exception_class"),
            "Exception message": saved_error.get("message"),
            "File size MB": saved_error.get("file_size_mb"),
            "Configured model": saved_error.get("configured_model"),
            "Effective model": saved_error.get("effective_model"),
            "Response format": saved_error.get("response_format"),
            "Timestamp granularities": saved_error.get("timestamp_granularities"),
            "API key detected": "Yes" if saved_error.get("api_key_detected") else "No",
            "Output directory": saved_error.get("output_directory"),
        })
        with st.expander("Technical Error Details"):
            st.code(saved_error.get("traceback", "No traceback captured."), language="text")
        if st.button("Clear Error", key=f"clear_avatar_error_{project.name}"):
            st.session_state.pop(error_key, None)
            st.rerun()

    transcribe_disabled = bool(blockers)
    if st.button("Transcribe Avatar Chunks", type="primary", disabled=transcribe_disabled, key=f"transcribe_avatars_{project.name}"):
        progress_box = st.empty()
        try:
            with st.spinner("Transcribing new or modified avatar chunks..."):
                result = transcribe_avatar_chunks(
                    discovery.chunks, transcript_dir, config,
                    progress=lambda message: progress_box.info(message),
                )
        except Exception as exc:
            trace = traceback.format_exc()
            logging.exception("Avatar transcription failed")
            log_path = transcript_dir / "avatar_transcription_error.log"
            try:
                transcript_dir.mkdir(parents=True, exist_ok=True)
                log_path.write_text(trace, encoding="utf-8", newline="\n")
            except OSError:
                logging.exception("Could not persist avatar transcription traceback to %s", log_path)
            settings = transcription_settings(config)
            details = getattr(exc, "details", {}) if isinstance(exc, AvatarTranscriptionError) else {}
            failed_chunk = details.get("failed_chunk") or getattr(getattr(exc, "chunk", None), "name", None)
            st.session_state[error_key] = {
                "failed_chunk": failed_chunk,
                "exception_class": type(exc.__cause__ or exc).__name__,
                "message": str(exc.__cause__ or exc),
                "file_size_mb": details.get("file_size_mb"),
                "configured_model": settings["configured_model"],
                "effective_model": settings["effective_model"],
                "response_format": settings["response_format"],
                "timestamp_granularities": settings["timestamp_granularities"],
                "api_key_detected": details.get("api_key_detected", bool(os.getenv(str(config.get("openai_api_key_env", "OPENAI_API_KEY"))))),
                "output_directory": str(transcript_dir),
                "traceback": trace,
            }
            st.rerun()
        else:
            st.session_state.pop(error_key, None)
            progress_box.success("All avatar chunks completed.")
            st.success(f"Transcription complete. Transcribed: {result.transcribed} · Reused: {result.reused} · Skipped: {result.skipped}")
            st.rerun()

    all_transcripts_present = bool(discovery and discovery.chunks) and all(
        transcript_cache_is_current(chunk, transcript_dir, config)
        for chunk in discovery.chunks
    )
    timeline_blockers = list(blockers)
    if not all_transcripts_present:
        timeline_blockers.append("Every avatar chunk must have current JSON and SRT outputs for the effective transcription model/settings.")

    if st.button("Build Actual Timeline", disabled=bool(timeline_blockers), key=f"build_actual_timeline_{project.name}"):
        try:
            with st.spinner("Aligning approved narration to actual spoken timing..."):
                result = build_actual_timeline(project, avatar_folder, config, transcript_dir=transcript_dir)
        except Exception as exc:
            st.error(f"Actual timeline generation failed: {type(exc).__name__}. Review avatar transcripts and production sheet.")
        else:
            if result.success:
                st.success(f"Actual timeline generated with {result.rows} scenes. Alignment: {result.alignment_score:.1f}%")
                try:
                    analytics_id = ensure_project_record(ANALYTICS_DB_PATH, project)
                    snap_rows = snapshot_actual_timeline(
                        ANALYTICS_DB_PATH,
                        analytics_id,
                        project / "08_actual_timeline.csv",
                        production_sheet_path=project / "07_production_sheet.csv",
                    )
                    st.caption(f"Analytics DB snapshot saved permanently: {snap_rows} timeline scenes.")
                except Exception as exc:
                    st.warning(f"Actual Timeline generated, but Analytics DB snapshot failed: {exc}")
                if result.warnings:
                    for warning in result.warnings:
                        st.warning(warning)
            else:
                st.error("Actual timeline was not generated because validation failed.")
                for item in result.missing_chunks + result.duplicate_chunks + result.warnings:
                    st.caption(f"• {item}")
            st.rerun()


    transcript_outputs = []
    if discovery and discovery.chunks:
        for chunk in discovery.chunks:
            j = transcript_dir / f"{chunk.path.stem}.json"
            s = transcript_dir / f"{chunk.path.stem}.srt"
            if j.is_file() or s.is_file():
                transcript_outputs.append((chunk.path.stem, j, s))

    if transcript_outputs:
        st.markdown("### Avatar Transcript Outputs")
        st.caption(f"Saved inside selected project: {transcript_dir}")
        rows = []
        for stem, j, s in transcript_outputs:
            rows.append({
                "Chunk": stem,
                "JSON": j.name if j.is_file() else "Missing",
                "SRT": s.name if s.is_file() else "Missing",
                "Folder": str(transcript_dir),
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    generated = [timeline_path, manifest_path, report_path]
    if any(path.is_file() for path in generated):
        st.markdown("### Avatar Timing Outputs")
        for path in generated:
            if path.is_file():
                mime = "text/csv" if path.suffix == ".csv" else ("application/json" if path.suffix == ".json" else "text/markdown")
                st.success(f"Generated: {path.name}")
                st.download_button(f"Download {path.name}", path.read_bytes(), file_name=path.name, mime=mime, key=f"download_avatar_timing_{project.name}_{path.name}")

    st.markdown("---")
    st.markdown("## Timeline Builder & CapCut Export")
    capcut_dir = project / "capcut"
    capcut_manifest = capcut_dir / "timeline_manifest.json"
    capcut_report = capcut_dir / "export_report.md"
    timeline_pass = timeline_path.is_file() and timeline_status == "PASS"
    if not timeline_path.is_file():
        st.caption("• 08_actual_timeline.csv must exist.")
    if timeline_path.is_file() and timeline_status != "PASS":
        st.caption("• Avatar Timeline status must be PASS.")
    if st.button("Generate CapCut Project", type="primary", disabled=not timeline_pass, key=f"generate_capcut_{project.name}"):
        try:
            with st.spinner("Building generic timeline manifest and CapCut Desktop project..."):
                built = build_timeline_manifest(project, timeline_path)
                exported = export_capcut_project(project, built.manifest_path)
        except (TimelineBuildError, CapCutExportError) as exc:
            st.error(f"CapCut export failed: {exc}")
        except FileNotFoundError as exc:
            logging.exception("CapCut export failed because a required filesystem path disappeared")
            capcut_dir.mkdir(parents=True, exist_ok=True)
            missing_path = getattr(exc, "filename", None) or str(exc)
            capcut_report.write_text(
                "# CapCut Export Report\n\n"
                "- Status: **FAIL**\n"
                "- Error: `FileNotFoundError`\n"
                f"- Missing path: `{missing_path}`\n"
                f"- Project root: `{project}`\n\n"
                "The exporter stopped before replacing the working project. "
                "Regenerate after confirming the reported path exists.\n",
                encoding="utf-8",
                newline="\n",
            )
            st.error(f"CapCut export failed: missing path {missing_path}. Review capcut/export_report.md.")
        except Exception as exc:
            logging.exception("CapCut export failed")
            st.error(f"CapCut export failed: {type(exc).__name__}. Review capcut/export_report.md.")
        else:
            
            if exported.warnings:
                st.warning("CapCut project generated: PROJECT GENERATED / PREVIEW READY. Visible image/B-roll placeholders remain and must be replaced before final production.")
                for warning in exported.warnings:
                    st.caption(f"• {warning}")
            else:
                st.success(f"CapCut project generated: FINAL ASSETS READY. Base avatar duration {exported.duration_seconds:.3f} seconds.")
            st.rerun()

    capcut_outputs = [capcut_manifest, capcut_dir / "asset_manifest.json", capcut_report,
                      capcut_dir / "CapCut_Project" / "draft_content.json",
                      capcut_dir / "CapCut_Project" / "draft_meta_info.json"]
    if any(path.is_file() for path in capcut_outputs):
        st.markdown("### CapCut Outputs")
        for path in capcut_outputs:
            if path.is_file():
                mime = "application/json" if path.suffix == ".json" else "text/markdown"
                st.success(f"Generated: {path.relative_to(project)}")
                st.download_button(f"Download {path.name}", path.read_bytes(), file_name=path.name, mime=mime, key=f"download_capcut_{project.name}_{path.name}_{len(str(path))}")


def load_production_sheet(path: Path) -> pd.DataFrame:
    try: return pd.read_csv(path)
    except Exception: return pd.DataFrame()


def find_asset_type_column(df: pd.DataFrame) -> str | None:
    for c in ["recommended_asset_type", "asset_type", "visual_type", "scene_type", "Asset Type", "Visual Type"]:
        if c in df.columns: return c
    return next((c for c in df.columns if "asset" in c.lower() and "type" in c.lower()), None)


def render_opus_image_prompt_import() -> None:
    st.subheader("Opus Image Prompt Import")
    project = project_selector("opus_image_prompt_import")
    if project is None:
        return

    st.caption(f"Selected Project: {project.name}")
    try:
        slots = load_production_ai_image_slots(project)
    except (FileNotFoundError, ValueError, UnicodeError) as exc:
        st.error(str(exc))
        return

    st.metric("Production AI_IMAGE Count", len(slots))
    st.caption(f"Authoritative Production source: {project / '07_production_sheet.csv'}")
    st.caption("Opus CSV Timing is legacy/reference-only and is never used by this importer.")

    existing_output = project / "10_image_prompts.md"
    if existing_output.is_file():
        st.warning("10_image_prompts.md already exists. Generating will replace it after creating a timestamped Backups/ copy.")

    uploaded = st.file_uploader("Upload Opus Prompt CSV", type=["csv"], key=f"opus_prompt_csv_{project.name}")
    if uploaded is None:
        st.info("Upload an Opus prompt CSV to validate mapping against the current project's Production Sheet.")
        return

    payload = uploaded.getvalue()
    try:
        validation = validate_import(project, payload)
    except (ValueError, UnicodeError, csv.Error) as exc:
        st.error(f"Could not parse Opus CSV: {exc}")
        return

    c1, c2 = st.columns(2)
    c1.metric("Imported Prompt Count", validation.imported_count)
    c2.metric("Validation Status", "PASS" if validation.passed else "FAIL")

    preview = pd.DataFrame([
        {
            "IMAGE": f"IMAGE {row.image_number:03d}",
            "Scene ID": row.scene_id,
            "Production Script Line": row.production_script_line,
            "Opus Script Line": row.opus_script_line,
            "Scene Type": row.scene_type,
            "Match Status": row.match_status,
        }
        for row in validation.mappings
    ])
    if not preview.empty:
        st.dataframe(preview, hide_index=True, width="stretch", key=f"opus_import_preview_{project.name}")

    if validation.errors:
        for error in validation.errors:
            st.error(error)

    generated_key = f"opus_generated_path_{project.name}"
    if st.button("Generate 10_image_prompts.md", type="primary", disabled=not validation.passed, key=f"generate_opus_prompts_{project.name}"):
        try:
            output, backup, _ = write_image_prompts(project, payload)
            st.session_state[generated_key] = str(output)
            st.success("10_image_prompts.md generated from the imported Opus prompts.")
            if backup:
                st.info(f"Backup created: {backup.relative_to(project)}")
        except (OSError, ValueError, UnicodeError) as exc:
            st.error(f"Could not generate 10_image_prompts.md: {exc}")

    generated = Path(st.session_state.get(generated_key, "")) if st.session_state.get(generated_key) else existing_output
    if generated.is_file() and validation.passed:
        st.download_button(
            "Download 10_image_prompts.md",
            data=generated.read_bytes(),
            file_name="10_image_prompts.md",
            mime="text/markdown",
            key=f"download_opus_prompts_{project.name}",
        )


def render_images() -> None:
    st.subheader("Image Generation")
    project = project_selector("images")
    if not project:
        return
    # Project path and all downstream state are resolved fresh on every Streamlit rerun/action.
    project = project.resolve()
    config = load_config()
    try:
        assignments = load_production_image_assignments(project)
    except ValueError as exc:
        st.error(str(exc)); return
    if not assignments:
        st.info("10_image_prompts.md is missing or has no Final AI IMAGE PROMPT entries. Generate the Production Package first.")
        return

    manifest = reconcile_manifest(project, assignments)
    records = manifest.get("images", {})
    generated = sum(1 for a in assignments if a.asset_path.is_file())
    stale_count = sum(1 for a in assignments if records.get(a.filename, {}).get("status") == "STALE")
    failed_count = sum(1 for a in assignments if records.get(a.filename, {}).get("status") == "FAILED")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("AI images required", len(assignments)); c2.metric("Already generated", generated)
    c3.metric("Remaining", len(assignments)-generated); c4.metric("Stale / Failed", f"{stale_count} / {failed_count}")
    st.caption(f"Production prompt source: {project / '10_image_prompts.md'} · Asset destination: {project / 'assets' / 'images'}")

    profiles = model_profiles_from_config(config)
    keys = list(profiles)
    default_key = str(config.get("image_generation_default_model", DEFAULT_MODEL_KEY))
    if default_key not in profiles: default_key = DEFAULT_MODEL_KEY if DEFAULT_MODEL_KEY in profiles else keys[0]
    model_key = st.selectbox("Image Model", keys, index=keys.index(default_key), format_func=lambda k: profiles[k].display_name, key=f"image_model_{project.name}")
    profile = profiles[model_key]
    enhancement = st.toggle("Prompt Enhancement", value=True, key=f"image_enhancement_{project.name}")
    st.caption(f"Provider: {profile.provider} · Model ID: {profile.model_id} · Output: {profile.dimensions[0]}×{profile.dimensions[1]} (16:9)")
    if not os.getenv("RUNWARE_API_KEY"):
        st.warning("RUNWARE_API_KEY is not configured. Preview/status works, but API generation is disabled.")

    remaining = len(select_missing(assignments))
    if profile.cost_per_image is not None:
        st.info(f"Estimated cost for {remaining} missing images: approximately ${remaining * profile.cost_per_image:.4f} (configuration-driven estimate).")

    st.markdown("### Prompt Preview")
    chosen_name = st.selectbox("Image", [a.filename for a in assignments], key=f"image_preview_{project.name}")
    chosen = next(a for a in assignments if a.filename == chosen_name)
    st.text_area("Original Production Prompt", chosen.original_prompt, height=180, disabled=True, key=f"original_prompt_{project.name}_{chosen_name}")
    st.text_area("Enhanced Generation Prompt", enhance_prompt(chosen.original_prompt, profile, enhancement), height=220, disabled=True, key=f"enhanced_prompt_{project.name}_{chosen_name}_{model_key}_{enhancement}")
    rec = records.get(chosen_name, {})
    if rec: st.caption(f"Status: {rec.get('status','PENDING')} · Previous model: {rec.get('selected_model','Unknown')} · Attempts: {rec.get('attempts',0)}")

    generated_names = [a.filename for a in assignments if a.asset_path.is_file()]
    selected_regen = st.multiselect("Select images to regenerate", generated_names, key=f"regen_images_{project.name}")
    retry_count = int(config.get("image_generation_retry_count", 2)); concurrency = int(config.get("image_generation_concurrency", 3))

    def run_generation(targets, label):
        if not targets: st.info(f"No images need {label.lower()}."); return
        if not os.getenv("RUNWARE_API_KEY"): st.error("RUNWARE_API_KEY is not configured."); return
        bar=st.progress(0); status=st.empty()
        def progress(done,total,result):
            bar.progress(done/total); status.write(f"{done} / {total} · {result.assignment.filename}: {result.status}")
        with st.spinner(f"{label}..."):
            results=generate_batch(project, targets, profile, enhancement, retry_count=retry_count, max_workers=concurrency, progress=progress)
        ok=sum(r.status=="SUCCESS" for r in results); bad=len(results)-ok
        (st.success if not bad else st.warning)(f"Completed: {ok} successful, {bad} failed.")
        st.rerun()

    b1,b2,b3,b4 = st.columns(4)
    if b1.button("Generate Missing Images", type="primary", key=f"gen_missing_{project.name}"):
        run_generation(select_missing(load_production_image_assignments(project)), "Generate Missing Images")
    if b2.button("Regenerate Selected", disabled=not selected_regen, key=f"regen_selected_{project.name}"):
        current=load_production_image_assignments(project); run_generation([a for a in current if a.filename in selected_regen], "Regenerate Selected")
    if b3.button("Retry Failed", key=f"retry_failed_{project.name}"):
        current=load_production_image_assignments(project); run_generation(select_failed_or_missing(project, current), "Retry Failed")
    if b4.button("Regenerate Stale Images", disabled=stale_count==0, key=f"regen_stale_{project.name}"):
        current=load_production_image_assignments(project); run_generation(select_stale(project, current), "Regenerate Stale Images")

    if st.button("Regenerate All With Current Model", key=f"regen_all_{project.name}"):
        run_generation(load_production_image_assignments(project), "Regenerate All")

    manifest = load_manifest(project)
    rows=[]
    for a in assignments:
        r=manifest.get("images",{}).get(a.filename,{})
        rows.append({"Image":a.filename,"Scene":a.scene_id,"Status":r.get("status","PENDING"),"Model":r.get("selected_model",""),"Attempts":r.get("attempts",0),"Error":r.get("safe_error_summary","")})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    zip_bytes=build_images_zip(project, assignments)
    st.download_button("Download Images ZIP", zip_bytes, file_name=f"{project.name}_images.zip", mime="application/zip", key=f"download_images_zip_{project.name}")


def render_text_overlay_import() -> None:
    st.subheader("Text Overlay Import")
    project = project_selector("text_overlay_import")
    if not project: return
    timeline_path = project / "08_actual_timeline.csv"
    artifact_path = project / ARTIFACT_NAME
    st.caption(f"Selected Project: {project.name}")
    st.caption(f"Authoritative Narration Source: {timeline_path}")
    st.caption(f"Actual Timeline Status: {'READY' if timeline_path.is_file() else 'MISSING'}")
    uploaded = st.file_uploader("Upload Opus Text Overlay CSV", type=["csv"], key=f"overlay_upload_{project.name}")
    state_key=f"overlay_validation_{project.name}"
    if uploaded is not None:
        try:
            rows=parse_opus_csv(uploaded.getvalue())
            st.metric("Imported Overlay Count", len(rows))
            if st.button("Validate Overlay CSV", type="primary", key=f"validate_overlay_{project.name}"):
                result=validate_rows(project, rows); st.session_state[state_key]=(rows,result)
        except Exception as exc:
            st.error(str(exc)); st.session_state.pop(state_key,None)
    else:
        st.metric("Imported Overlay Count", 0)

    saved=st.session_state.get(state_key)
    result=saved[1] if saved else None
    st.metric("Validation Status", "PASS" if result and result.passed else ("FAIL" if result else "NOT RUN"))
    if result:
        preview=[]
        for r in result.records:
            preview.append({"Overlay":r.overlay_number,"Type":r.overlay_type,"Script Line Start":r.script_line_start,"Script Line End":r.script_line_end,"Overlay Text":r.overlay_text,"Timing Match":r.timing_source,"Start":r.start_seconds,"End":r.end_seconds,"Status":r.status})
        st.dataframe(pd.DataFrame(preview), hide_index=True, use_container_width=True)
        for error in result.errors: st.error(error)
        for warning in result.warnings: st.warning(warning)
    if artifact_path.exists(): st.warning(f"{ARTIFACT_NAME} already exists. Regeneration will create a timestamped backup first.")
    generate_disabled=not (result and result.passed)
    if st.button("Generate Text Overlay Artifact", disabled=generate_disabled, key=f"generate_overlay_{project.name}"):
        try:
            path=write_artifact(project,result); st.success(f"Generated: {path.name}")
        except Exception as exc: st.error(str(exc))
    if artifact_path.is_file():
        st.download_button("Download Text Overlay Artifact", artifact_path.read_bytes(), file_name=artifact_path.name, mime="text/csv", key=f"download_overlay_{project.name}")


def render_files() -> None:
    st.subheader("File Manager")
    project = project_selector("files")
    if not project: return
    files = sorted([p for p in project.rglob("*") if p.is_file() and p.suffix.lower() in VIEWABLE_SUFFIXES], key=lambda p: str(p).lower())
    if not files: st.info("No viewable files found."); return
    labels = [str(p.relative_to(project)) for p in files]; name = st.selectbox("File", labels); path = project / name
    if path.suffix.lower() == ".csv":
        try: st.dataframe(pd.read_csv(path), width="stretch")
        except Exception as exc: st.error(str(exc))
        st.download_button("Download", path.read_bytes(), file_name=path.name); return
    text = safe_read_text(path); edited = st.text_area("Content", text, height=560); c1, c2 = st.columns(2)
    if c1.button("Save", type="primary") and path.suffix.lower() in EDITABLE_SUFFIXES:
        if path.suffix.lower() == ".json":
            try: edited = json.dumps(json.loads(edited), indent=2, ensure_ascii=False) + "\n"
            except json.JSONDecodeError as exc: st.error(f"Invalid JSON: {exc}"); return
        safe_write_text(path, edited); st.success("Saved.")
    c2.download_button("Download", text, file_name=path.name)


def render_runtime_authority_notice(config: dict[str, Any]) -> None:
    """Warn when a second runtime authority disagrees with config.json."""
    conflicts = runtime_config_conflicts(config)
    if conflicts:
        st.warning(
            "Runtime authority conflict — two different runtime bases are configured. "
            "Narrative QA uses config.json, so any other source will disagree:\n\n"
            + "\n".join(f"- {c}" for c in conflicts)
        )


def render_config() -> None:
    st.subheader("System Configuration")
    config = load_config(); config.setdefault("production_defaults", {"avatar": 40, "ai_images": 30, "stock": 10, "overlays": 20})
    st.markdown("### General")
    config["channel_name"] = st.text_input("Channel name", config.get("channel_name", "")); config["host_name"] = st.text_input("Host name", config.get("host_name", "")); config["target_runtime_minutes"] = st.number_input("Target runtime", 5, 60, int(config.get("target_runtime_minutes", 25)))
    st.markdown("### Codex CLI")
    config["codex_cli_command"] = st.text_input("CLI command template", config.get("codex_cli_command", ""), help='Recommended: codex.cmd exec --sandbox workspace-write --skip-git-repo-check {prompt}')
    config["direct_run_enabled"] = st.checkbox("Direct Run enabled", bool(config.get("direct_run_enabled", True)))
    config["speech_optimizer_required_for_production"] = st.checkbox("Require Speech Optimizer before production", bool(config.get("speech_optimizer_required_for_production", True)))
    config["allow_production_override"] = st.checkbox("Allow manual Production Lock override", bool(config.get("allow_production_override", False)))
    st.markdown("### Raw JSON")
    raw = st.text_area("config.json", json.dumps(config, indent=2, ensure_ascii=False), height=440)
    if st.button("Validate and Save", type="primary"):
        try: parsed = json.loads(raw)
        except json.JSONDecodeError as exc: st.error(f"Invalid JSON: {exc}"); return
        save_config(parsed); st.success("Configuration saved.")



def render_analytics() -> None:
    st.subheader("Permanent YouTube Analytics")
    st.caption(
        "Projects are temporary production workspaces; this Analytics database is permanent. "
        "Deleting a project folder does not delete its analytics, timeline snapshot, or transcript snapshot."
    )
    ANALYTICS_DIR.mkdir(exist_ok=True)
    init_db(ANALYTICS_DB_PATH)
    try:
        cleanup = repair_reconstructed_transcript_overlaps(ANALYTICS_DB_PATH)
        if cleanup.get("videos"):
            sync_active_channel_script_rules(ANALYTICS_DB_PATH)
        write_active_channel_rules_file(ANALYTICS_DB_PATH, ACTIVE_CHANNEL_RULES_PATH)
    except Exception as exc:
        st.warning(f"Active channel script rules could not sync: {exc}")

    with st.expander("YouTube API Connection", expanded=not YOUTUBE_OAUTH_TOKEN_PATH.is_file()):
        st.caption(
            "Use a Google OAuth Desktop-app JSON. Senior Health AI shows the authorization URL so you can paste it into IX Browser. "
            "The Google callback returns only to 127.0.0.1 on this PC; the old copy/paste authorization-code flow is not used."
        )
        oauth_upload = st.file_uploader(
            "Google OAuth Desktop client JSON",
            type=["json"],
            key="youtube_oauth_client_upload",
            help="Create a Desktop app OAuth client in Google Cloud with YouTube Data API v3 and YouTube Analytics API enabled.",
        )
        if oauth_upload is not None and st.button("Save YouTube OAuth Client", key="save_youtube_oauth_client"):
            try:
                payload = oauth_upload.getvalue()
                parsed = json.loads(payload.decode("utf-8-sig"))
                cfg = parsed.get("installed") or parsed.get("web") or {}
                if not cfg.get("client_id") or not cfg.get("client_secret"):
                    raise ValueError("This does not look like a Google OAuth Desktop client JSON.")
                ANALYTICS_DIR.mkdir(exist_ok=True)
                YOUTUBE_OAUTH_CLIENT_PATH.write_bytes(payload)
                st.success("YouTube OAuth client saved locally under Analytics. It is not added to project files.")
            except Exception as exc:
                st.error(f"Could not save OAuth client: {exc}")

        status = youtube_connection_status(YOUTUBE_OAUTH_CLIENT_PATH, YOUTUBE_OAUTH_TOKEN_PATH)
        if status.get("connected"):
            st.success(f"YouTube connected: {status.get('channel_title') or status.get('channel_id')}")
        elif status.get("error"):
            st.warning(f"YouTube not connected: {status.get('error')}")
        else:
            st.info("YouTube is not connected yet.")

        c_auth, c_sync = st.columns(2)
        with c_auth:
            if st.button("Generate IX Browser Authorization Link", key="youtube_generate_auth_link", disabled=not YOUTUBE_OAUTH_CLIENT_PATH.is_file()):
                try:
                    auth_url = start_manual_oauth(
                        YOUTUBE_OAUTH_CLIENT_PATH, YOUTUBE_OAUTH_TOKEN_PATH, YOUTUBE_OAUTH_PENDING_PATH
                    )
                    st.session_state["youtube_manual_auth_url"] = auth_url
                except Exception as exc:
                    st.error(f"Could not start YouTube connection: {exc}")
            auth_url = st.session_state.get("youtube_manual_auth_url")
            if auth_url:
                st.text_area(
                    "Copy this URL into IX Browser",
                    value=auth_url,
                    height=120,
                    key="youtube_manual_auth_url_box",
                )
                st.caption("Keep Senior Health AI running while you approve access in IX Browser, then return here and click Refresh Connection Status.")
            if st.button("Refresh Connection Status", key="youtube_refresh_connection_status"):
                st.rerun()

        with c_sync:
            if st.button("Sync YouTube Analytics", type="primary", key="youtube_api_sync", disabled=not status.get("connected")):
                try:
                    sync_result = sync_youtube_channel(
                        ANALYTICS_DB_PATH, YOUTUBE_OAUTH_CLIENT_PATH, YOUTUBE_OAUTH_TOKEN_PATH
                    )
                    learning_sync = write_active_channel_rules_file(
                        ANALYTICS_DB_PATH, ACTIVE_CHANNEL_RULES_PATH
                    )
                    thumbnail_learning = auto_sync_thumbnail_learning(
                        ANALYTICS_DB_PATH,
                        ACTIVE_CHANNEL_PACKAGING_RULES_PATH,
                        model=str(load_config().get("thumbnail_analysis_model", "gpt-5.6-luna")),
                    )
                    st.success(
                        f"YouTube sync complete: {sync_result.get('uploaded_videos', 0)} uploaded video(s) checked, "
                        f"{sync_result.get('performance_synced', 0)} performance snapshot(s), "
                        f"{sync_result.get('retention_synced', 0)} retention curve(s), "
                        f"{sync_result.get('caption_transcripts_synced', 0)} permanent caption transcript(s), "
                        f"{sync_result.get('reach_reports_imported', 0)} new reach/CTR report(s)."
                    )
                    if sync_result.get("reach_job_created"):
                        st.info(
                            "YouTube Reporting reach job created for thumbnail Impressions + CTR. "
                            "YouTube normally generates the first report within 24 hours and historical reports "
                            "for roughly the prior 30 days arrive as they become available. Run Sync again later."
                        )
                    elif sync_result.get("reach_waiting_for_first_report"):
                        st.caption(
                            "CTR reporting job exists, but its first reach report is not available yet. "
                            "Content/retention learning continues without CTR."
                        )
                    elif sync_result.get("reach_reports_available"):
                        st.caption(
                            f"Reach/CTR: {sync_result.get('reach_reports_available', 0)} report(s) available; "
                            f"{sync_result.get('reach_rows_written', 0)} video-day row(s) stored this sync. "
                            "Already processed reports are not downloaded again."
                        )
                    if sync_result.get("no_analytics_yet"):
                        st.caption(f"{sync_result.get('no_analytics_yet')} uploaded video(s) do not have Analytics data available yet.")
                    if sync_result.get("retention_unavailable"):
                        st.warning(
                            f"Retention unavailable/skipped for {sync_result.get('retention_unavailable', 0)} video(s). "
                            "Open Retention sync diagnostics below for the exact YouTube Video ID and API row count."
                        )
                    if sync_result.get("retention_diagnostics"):
                        with st.expander("Retention sync diagnostics"):
                            for diagnostic in sync_result["retention_diagnostics"]:
                                st.write(f"• {diagnostic}")
                    if sync_result.get("caption_transcripts_unavailable"):
                        st.caption(
                            f"{sync_result.get('caption_transcripts_unavailable')} video(s) had no downloadable YouTube caption track yet. "
                            "They will be retried on a later sync; manual transcript remains only a fallback."
                        )
                    if sync_result.get("caption_reauthorization_required"):
                        st.warning(
                            "Caption access needs the new YouTube permission. Click Generate IX Browser Authorization Link once, "
                            "approve access again in IX Browser, then run Sync YouTube Analytics again."
                        )
                    if sync_result.get("errors"):
                        with st.expander("YouTube sync warnings"):
                            for err in sync_result["errors"]:
                                st.write(f"• {err}")
                    thumb = thumbnail_learning.get("thumbnails") or {}
                    vision = thumbnail_learning.get("analysis") or {}
                    joined = thumbnail_learning.get("ctr_join") or {}
                    candidates = thumbnail_learning.get("candidates") or {}
                    st.info(
                        "Thumbnail learning refreshed automatically: "
                        f"{thumb.get('checked', 0)} current thumbnail(s) checked by Video ID · "
                        f"{thumb.get('downloaded', 0)} new/changed · {thumb.get('unchanged', 0)} unchanged · "
                        f"{vision.get('analyzed', 0)} newly vision-analyzed · "
                        f"{joined.get('joined', 0)} CTR evidence record(s) joined · "
                        f"{candidates.get('created', 0)} new candidate rule(s)."
                    )
                    if thumbnail_learning.get("warnings"):
                        with st.expander("Automatic thumbnail-learning diagnostics"):
                            for warning in thumbnail_learning["warnings"]:
                                st.write(f"• {warning}")
                    st.caption(
                        "Only videos actually present in the channel uploads playlist are synced. Local/unuploaded project records stay archived but are excluded from YouTube performance learning. "
                        f"Script learning rules were refreshed automatically ({learning_sync.get('active', 0)} active rule(s)). "
                        "Thumbnail archive, text/visual extraction, CTR attribution, comparisons, and candidate refresh now run automatically from this same sync."
                    )
                except Exception as exc:
                    st.error(f"YouTube sync failed: {exc}")

    if st.button("Refresh Project Analytics Assets", key="analytics_refresh_project_assets"):
        try:
            refreshed = auto_link_existing_projects(ANALYTICS_DB_PATH, PROJECTS_DIR)
            mark_missing_project_folders(ANALYTICS_DB_PATH)
            st.success(
                "Project Analytics refresh complete: "
                f"{refreshed.get('scanned', 0)} project(s) checked, "
                f"{refreshed.get('registered', 0)} registered, "
                f"{refreshed.get('linked', 0)} linked, "
                f"{refreshed.get('timelines', 0)} timeline snapshot(s) refreshed. "
                "Existing permanent script/timeline assets were kept; missing or changed project assets were copied into Analytics."
            )
        except Exception as exc:
            st.error(f"Project Analytics refresh failed: {exc}")

    # Backfill/link projects that existed before Analytics DB was installed.
    # Exact normalized title matches upgrade the SAME youtube_only row, preserving imports.
    try:
        backfill = auto_link_existing_projects(ANALYTICS_DB_PATH, PROJECTS_DIR)
        if backfill.get("linked") or backfill.get("registered") or backfill.get("timelines"):
            st.caption(
                f"Existing-project sync: {backfill.get('linked', 0)} linked, "
                f"{backfill.get('registered', 0)} registered, "
                f"{backfill.get('timelines', 0)} timeline snapshot(s)."
            )
    except Exception as exc:
        st.warning(f"Existing-project analytics sync could not complete: {exc}")

    # Keep project-folder lifecycle status current without deleting anything.
    try:
        mark_missing_project_folders(ANALYTICS_DB_PATH)
    except Exception:
        pass

    tabs = st.tabs(["Dashboard", "Learning Engine", "Retention Mapping", "Content / Performance", "Video Registry", "YouTube Video Link", "CTR / Thumbnails", "Import Single Video", "Timeline / Transcript", "Video Detail"])

    with tabs[0]:
        st.markdown("### Channel Analytics Dashboard")
        st.caption(
            "Read-only summary from the permanent analytics DB. "
            "Uses each video's latest imported Content/Performance snapshot."
        )

        dashboard = channel_dashboard_data(ANALYTICS_DB_PATH)
        dash_df = dashboard.get("videos")
        summary = dashboard.get("summary") or {}

        if dash_df is None or dash_df.empty:
            st.info("No analytics data yet. Import the channel-wide Content/Performance CSV first.")
        else:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Videos with analytics", int(summary.get("videos_with_analytics", 0)))
            c2.metric("Total views", f"{summary.get('total_views', 0):,.0f}")
            avg_ctr = summary.get("avg_ctr")
            c3.metric("Avg CTR", "-" if avg_ctr is None else f"{avg_ctr:.2f}%")
            avg_apv = summary.get("avg_apv")
            c4.metric("Avg % Viewed", "-" if avg_apv is None else f"{avg_apv:.2f}%")

            d1, d2, d3, d4 = st.columns(4)
            avd = summary.get("avg_avd_seconds")
            avd_label = "-" if avd is None else f"{int(round(avd))//60}:{int(round(avd))%60:02d}"
            d1.metric("Avg AVD", avd_label)
            d2.metric("Watch time", f"{summary.get('total_watch_hours', 0):,.1f} h")
            subs = summary.get("total_subscribers")
            d3.metric("Subscribers", "-" if subs is None else f"{subs:,.0f}")
            d4.metric("Registered videos", int(summary.get("registered_videos", 0)))

            scored = dash_df[dash_df["views"].notna()].copy()

            st.markdown("#### Performance diagnosis")
            if not scored.empty:
                med_ctr = scored["ctr_percent"].median(skipna=True)
                med_apv = scored["average_percentage_viewed"].median(skipna=True)

                def diagnose(row):
                    ctr = row.get("ctr_percent")
                    apv = row.get("average_percentage_viewed")
                    if pd.isna(ctr) or pd.isna(apv) or pd.isna(med_ctr) or pd.isna(med_apv):
                        return "INSUFFICIENT DATA"
                    if ctr >= med_ctr and apv >= med_apv:
                        return "STRONG"
                    if ctr < med_ctr and apv >= med_apv:
                        return "PACKAGING OPPORTUNITY"
                    if ctr >= med_ctr and apv < med_apv:
                        return "CONTENT HOLD OPPORTUNITY"
                    return "PACKAGING + CONTENT"

                scored["Diagnosis"] = scored.apply(diagnose, axis=1)
                scored["CTR %"] = scored["ctr_percent"].map(lambda x: None if pd.isna(x) else round(float(x), 2))
                scored["Avg % Viewed"] = scored["average_percentage_viewed"].map(lambda x: None if pd.isna(x) else round(float(x), 2))
                scored["AVD"] = scored["average_view_duration_seconds"].map(
                    lambda x: "-" if pd.isna(x) else f"{int(round(x))//60}:{int(round(x))%60:02d}"
                )

                diag_cols = ["title","publish_date","publish_weekday","views","CTR %","Avg % Viewed","AVD","Diagnosis"]
                diag_cols = [c for c in diag_cols if c in scored.columns]
                st.dataframe(
                    scored[diag_cols].rename(columns={
                        "title":"Title",
                        "publish_date":"Publish Date",
                        "publish_weekday":"Publish Day",
                        "views":"Views",
                    }),
                    width="stretch",
                    hide_index=True,
                )

                st.caption(
                    "Diagnosis uses your current channel medians: low CTR points to packaging; "
                    "low Average % Viewed points to content hold. It is relative to your channel, not a universal benchmark."
                )

                st.markdown("#### Top videos")
                top_views = scored.sort_values("views", ascending=False).head(10).copy()
                top_views["CTR %"] = top_views["ctr_percent"].map(lambda x: None if pd.isna(x) else round(float(x), 2))
                top_views["Avg % Viewed"] = top_views["average_percentage_viewed"].map(lambda x: None if pd.isna(x) else round(float(x), 2))
                st.dataframe(
                    top_views[["title","views","CTR %","Avg % Viewed"]].rename(columns={
                        "title":"Title","views":"Views"
                    }),
                    width="stretch",
                    hide_index=True,
                )

            st.markdown("#### Publish Day Performance")
            weekday_df = weekday_performance_summary(ANALYTICS_DB_PATH)
            if weekday_df.empty:
                st.info("No publish-day data yet.")
            else:
                weekday_show = weekday_df.copy()
                weekday_show["AVD"] = weekday_show["avg_avd_seconds"].map(
                    lambda x: "-" if pd.isna(x) else f"{int(round(x))//60}:{int(round(x))%60:02d}"
                )
                weekday_show = weekday_show.rename(columns={
                    "weekday":"Publish Day",
                    "videos":"Videos",
                    "avg_ctr":"Avg CTR %",
                    "avg_apv":"Avg % Viewed",
                    "avg_views":"Avg Views",
                })
                cols = ["Publish Day","Videos","Avg CTR %","Avg % Viewed","AVD","Avg Views"]
                st.dataframe(weekday_show[cols], width="stretch", hide_index=True)

    with tabs[1]:
        st.markdown("### Winner / Loser Learning Engine")
        st.caption(
            "Learns from your own channel. Low-sample videos are kept as Early Signal "
            "and do not become mature winner references."
        )

        learning = winner_loser_learning_data(ANALYTICS_DB_PATH)
        learn_df = learning.get("videos")
        learn_summary = learning.get("summary") or {}

        if learn_df is None or learn_df.empty:
            st.info("Not enough Average % Viewed data yet. Run YouTube Analytics sync or import Content/Performance data first.")
        else:
            a, b, c, d, e, f = st.columns(6)
            a.metric("Full strong", int(learn_summary.get("strong", 0)))
            b.metric("Content strong", int(learn_summary.get("content_strong_pending", 0)))
            c.metric("Packaging opportunity", int(learn_summary.get("packaging", 0)))
            d.metric(
                "Content hold",
                int(learn_summary.get("content_hold", 0)) + int(learn_summary.get("content_hold_pending", 0)),
            )
            e.metric("Packaging + content", int(learn_summary.get("both", 0)))
            f.metric("CTR pending", int(learn_summary.get("ctr_pending", 0)))

            median_ctr = learn_summary.get("median_ctr")
            ctr_text = "pending" if median_ctr is None else f"{float(median_ctr):.2f}%"
            st.caption(
                f"Channel baselines: median CTR {ctr_text} · "
                f"median Average % Viewed {learn_summary.get('median_apv', 0):.2f}% · "
                f"{int(learn_summary.get('videos_analyzed', 0))} videos analyzed · "
                f"{int(learn_summary.get('videos_learning_eligible', 0))} learning-eligible. "
                "Content learning does not wait for CTR."
            )
            st.caption(
                "Evidence maturity: MATURE = 100+ views or 1,000+ impressions · "
                "DEVELOPING = 30+ views or 300+ impressions · EARLY = below both."
            )

            st.markdown("#### What to work on next")
            for rec in learning.get("recommendations", []):
                st.write(f"• {rec}")

            st.markdown("#### Content winner reference set")
            winners = learn_df[
                (learn_df["base_diagnosis"].isin(["STRONG", "CONTENT STRONG · CTR PENDING"])) &
                (learn_df["evidence_maturity"] != "EARLY")
            ].copy()
            if winners.empty:
                st.info("No learning-eligible content-strong reference videos yet.")
            else:
                winners = winners.sort_values(["learning_score","views"], ascending=[False,False])
                winners["CTR %"] = pd.to_numeric(winners["ctr_percent"], errors="coerce").round(2)
                winners["Avg % Viewed"] = pd.to_numeric(winners["average_percentage_viewed"], errors="coerce").round(2)
                winners["Score"] = pd.to_numeric(winners["learning_score"], errors="coerce").round(1)
                winners["AVD"] = winners["average_view_duration_seconds"].map(
                    lambda x: "-" if pd.isna(x) else f"{int(round(x))//60}:{int(round(x))%60:02d}"
                )
                st.dataframe(
                    winners[["title","publish_date","publish_weekday","views","impressions","CTR %","Avg % Viewed","AVD","evidence_maturity","Score"]]
                    .rename(columns={
                        "title":"Title","publish_date":"Publish Date","publish_weekday":"Publish Day",
                        "views":"Views","impressions":"Impressions","evidence_maturity":"Evidence"
                    }),
                    width="stretch", hide_index=True
                )

            st.markdown("#### Pattern Learning")
            patterns = learning.get("patterns")
            if patterns is None or patterns.empty:
                st.caption("Not enough repeated title patterns in learning-eligible videos yet.")
            else:
                p = patterns.copy()
                for col in ["Avg CTR %","Avg % Viewed","Strong Rate %"]:
                    p[col] = pd.to_numeric(p[col], errors="coerce").round(2)
                st.dataframe(p, width="stretch", hide_index=True)
                st.caption(
                    "These are descriptive correlations from your own eligible videos, not causal rules. "
                    "Average % Viewed patterns continue even while CTR is pending; packaging conclusions require CTR."
                )


            st.markdown("#### Cross-Video Script Pattern Learning")
            st.caption(
                "This aggregates retention-linked script diagnoses across videos. "
                "A finding becomes a CHANNEL PATTERN only after the same issue appears in 3+ learning-eligible videos."
            )
            cross = cross_video_script_pattern_learning(ANALYTICS_DB_PATH)
            cross_summary = cross.get("summary") or {}
            cross_patterns = cross.get("patterns")
            cross_events = cross.get("events")

            x1, x2, x3, x4 = st.columns(4)
            x1.metric("Videos mapped", int(cross_summary.get("videos_with_script_retention", 0)))
            x2.metric("Learning-eligible", int(cross_summary.get("learning_eligible_videos", 0)))
            x3.metric("Channel patterns", int(cross_summary.get("channel_patterns", 0)))
            x4.metric("Repeated signals", int(cross_summary.get("repeated_signals", 0)))

            if cross_patterns is None or cross_patterns.empty:
                st.info(
                    "Not enough retention + transcript data across videos yet. "
                    "Import each video's All.csv and attach its timeline/transcript; patterns will appear automatically."
                )
            else:
                cp = cross_patterns.copy()
                cp["Avg Drop"] = pd.to_numeric(cp["Avg Drop"], errors="coerce").round(2)
                cp["Median Drop"] = pd.to_numeric(cp["Median Drop"], errors="coerce").round(2)
                cp["Priority Score"] = pd.to_numeric(cp["Priority Score"], errors="coerce").round(1)
                st.dataframe(
                    cp[[
                        "Script Pattern","Videos","Events","Avg Drop","Median Drop",
                        "Opening Videos","Confidence","Future Script Rule"
                    ]],
                    width="stretch",
                    hide_index=True,
                )

                promoted = cp[cp["Confidence"] == "CHANNEL PATTERN"].copy()
                if not promoted.empty:
                    st.success(
                        f"{len(promoted)} script issue(s) currently meet the 3+ video threshold "
                        "for channel-level learning."
                    )
                    for _, row in promoted.iterrows():
                        st.write(
                            f"• **{row['Script Pattern']}** — seen in {int(row['Videos'])} videos; "
                            f"avg retention change {row['Avg Drop']:.2f}. "
                            f"Working rule: {row['Future Script Rule']}"
                        )
                else:
                    st.caption(
                        "No script issue has reached the 3-video channel-pattern threshold yet. "
                        "The engine will keep accumulating evidence as more retention files are added."
                    )

                with st.expander("Evidence behind script patterns"):
                    ev = cross_events.copy()
                    ev = ev[ev["learning_eligible"]].copy()
                    if ev.empty:
                        st.info("No learning-eligible evidence rows yet.")
                    else:
                        ev["Time Window"] = ev.apply(
                            lambda r: (
                                f"{int(float(r['start_sec']))//60}:{int(float(r['start_sec']))%60:02d}–"
                                f"{int(float(r['end_sec']))//60}:{int(float(r['end_sec']))%60:02d}"
                            ),
                            axis=1,
                        )
                        ev["Drop"] = pd.to_numeric(ev["retention_delta"], errors="coerce").round(2)
                        st.dataframe(
                            ev[[
                                "title","Time Window","event","primary_issue","Drop",
                                "future_rule","script_text"
                            ]].rename(columns={
                                "title":"Video",
                                "event":"Event",
                                "primary_issue":"Primary Script Issue",
                                "future_rule":"Future Script Rule",
                                "script_text":"Script / Transcript",
                            }),
                            width="stretch",
                            hide_index=True,
                        )

            st.warning(
                "Cross-video script patterns are evidence-backed hypotheses, not proof of causation. "
                "Only repeated learning-eligible signals should influence future writing rules."
            )


            st.markdown("#### Active Channel Script Rules — Auto Applied")
            try:
                rule_sync = write_active_channel_rules_file(
                    ANALYTICS_DB_PATH, ACTIVE_CHANNEL_RULES_PATH
                )
                active_rules = active_channel_script_rules(ANALYTICS_DB_PATH)
                all_rules = all_channel_script_rules(ANALYTICS_DB_PATH)

                r1, r2, r3 = st.columns(3)
                r1.metric("ACTIVE rules", int(rule_sync.get("active", 0)))
                r2.metric("Activated this sync", int(rule_sync.get("activated", 0)))
                r3.metric("Retired this sync", int(rule_sync.get("retired", 0)))

                if active_rules.empty:
                    st.info(
                        "No rule has reached ACTIVE status yet. A script issue activates automatically "
                        "after it appears in 3+ learning-eligible videos."
                    )
                else:
                    view = active_rules.copy()
                    view["Avg Drop"] = pd.to_numeric(view["avg_drop"], errors="coerce").round(2)
                    st.dataframe(
                        view[[
                            "script_pattern","rule_text","videos","events","Avg Drop","activated_at"
                        ]].rename(columns={
                            "script_pattern":"Script Pattern",
                            "rule_text":"Auto Writer Rule",
                            "videos":"Videos",
                            "events":"Events",
                            "activated_at":"Activated",
                        }),
                        width="stretch",
                        hide_index=True,
                    )
                    st.success(
                        "These ACTIVE rules are automatically injected into future Script Outline / "
                        "Prepare Opus Package instructions and the Writer Workspace package download."
                    )

                with st.expander("Rule lifecycle audit"):
                    if all_rules.empty:
                        st.caption("No learned rules yet.")
                    else:
                        audit = all_rules.copy()
                        audit["Avg Drop"] = pd.to_numeric(audit["avg_drop"], errors="coerce").round(2)
                        st.dataframe(
                            audit[[
                                "script_pattern","status","videos","events","Avg Drop",
                                "first_seen_at","activated_at","retired_at"
                            ]].rename(columns={
                                "script_pattern":"Script Pattern",
                                "status":"Status",
                                "videos":"Videos",
                                "events":"Events",
                                "first_seen_at":"First Seen",
                                "activated_at":"Activated",
                                "retired_at":"Retired",
                            }),
                            width="stretch",
                            hide_index=True,
                        )
            except Exception as exc:
                st.error(f"Active rule sync failed: {exc}")

            if int(learn_summary.get("videos_with_ctr", 0)) == 0:
                st.info(
                    "Packaging learning is waiting for YouTube Reporting API reach data. "
                    "Script/content learning below is already active from Average % Viewed, AVD and retention."
                )

            st.markdown("#### Packaging opportunities")
            pack = learn_df[
                (learn_df["base_diagnosis"] == "PACKAGING OPPORTUNITY") &
                (learn_df["evidence_maturity"] != "EARLY")
            ].copy()
            if not pack.empty:
                pack["CTR %"] = pd.to_numeric(pack["ctr_percent"], errors="coerce").round(2)
                pack["Avg % Viewed"] = pd.to_numeric(pack["average_percentage_viewed"], errors="coerce").round(2)
                st.dataframe(
                    pack.sort_values(["average_percentage_viewed","ctr_percent"], ascending=[False,True])
                    [["title","views","impressions","CTR %","Avg % Viewed","evidence_maturity"]]
                    .rename(columns={"title":"Title","views":"Views","impressions":"Impressions","evidence_maturity":"Evidence"}),
                    width="stretch", hide_index=True
                )
            else:
                st.caption("No learning-eligible packaging opportunities.")

            st.markdown("#### Content hold opportunities")
            hold = learn_df[
                (learn_df["base_diagnosis"].isin(["CONTENT HOLD OPPORTUNITY", "CONTENT HOLD OPPORTUNITY · CTR PENDING"])) &
                (learn_df["evidence_maturity"] != "EARLY")
            ].copy()
            if not hold.empty:
                hold["CTR %"] = pd.to_numeric(hold["ctr_percent"], errors="coerce").round(2)
                hold["Avg % Viewed"] = pd.to_numeric(hold["average_percentage_viewed"], errors="coerce").round(2)
                hold["AVD"] = hold["average_view_duration_seconds"].map(
                    lambda x: "-" if pd.isna(x) else f"{int(round(x))//60}:{int(round(x))%60:02d}"
                )
                st.dataframe(
                    hold.sort_values(["ctr_percent","average_percentage_viewed"], ascending=[False,True])
                    [["title","views","impressions","CTR %","Avg % Viewed","AVD","evidence_maturity"]]
                    .rename(columns={"title":"Title","views":"Views","impressions":"Impressions","evidence_maturity":"Evidence"}),
                    width="stretch", hide_index=True
                )
            else:
                st.caption("No learning-eligible content-hold opportunities.")

            st.markdown("#### Full review candidates")
            both = learn_df[
                (learn_df["base_diagnosis"] == "PACKAGING + CONTENT") &
                (learn_df["evidence_maturity"] != "EARLY")
            ].copy()
            if not both.empty:
                both["CTR %"] = pd.to_numeric(both["ctr_percent"], errors="coerce").round(2)
                both["Avg % Viewed"] = pd.to_numeric(both["average_percentage_viewed"], errors="coerce").round(2)
                st.dataframe(
                    both.sort_values("learning_score")
                    [["title","views","impressions","CTR %","Avg % Viewed","evidence_maturity"]]
                    .rename(columns={"title":"Title","views":"Views","impressions":"Impressions","evidence_maturity":"Evidence"}),
                    width="stretch", hide_index=True
                )
            else:
                st.caption("No learning-eligible full-review candidates.")

            st.markdown("#### Early signals — wait for more data")
            early = learn_df[learn_df["evidence_maturity"] == "EARLY"].copy()
            if early.empty:
                st.caption("No early-signal videos.")
            else:
                early["CTR %"] = pd.to_numeric(early["ctr_percent"], errors="coerce").round(2)
                early["Avg % Viewed"] = pd.to_numeric(early["average_percentage_viewed"], errors="coerce").round(2)
                st.dataframe(
                    early[["title","views","impressions","CTR %","Avg % Viewed","base_diagnosis"]]
                    .rename(columns={
                        "title":"Title","views":"Views","impressions":"Impressions",
                        "base_diagnosis":"Provisional signal"
                    }),
                    width="stretch", hide_index=True
                )

            st.info(
                "Exact scene-level mistakes still require retention-curve data mapped to the stored "
                "Actual Timeline or timestamped transcript."
            )

    with tabs[2]:
        st.markdown("### Scene-Level Retention Mapping")
        st.caption(
            "Upload a true audience-retention curve for one video. The system maps each retention point "
            "to the permanent Actual Timeline (S###) or timestamped transcript (TS####). "
            "A normal Average % Viewed summary CSV is not accepted here."
        )

        retention_videos = list_videos(ANALYTICS_DB_PATH)
        retention_options = [
            v for v in retention_videos
            if str(v.get("youtube_video_id") or "").strip() and v.get("project_id")
        ]

        if not retention_options:
            st.info("No videos are registered yet.")
        else:
            retention_map = {
                v["analytics_id"]: (
                    f"{v.get('youtube_title') or v.get('locked_title') or v.get('project_slug') or v['analytics_id']}"
                    f" · {v.get('youtube_video_id') or 'no video id'}"
                )
                for v in retention_options
            }
            retention_ids = list(retention_map)
            retention_id = st.selectbox(
                "Video",
                retention_ids,
                format_func=lambda x: retention_map[x],
                key="retention_mapping_video",
            )
            retention_rec = get_video(ANALYTICS_DB_PATH, retention_id) or {}

            # Mapping provenance: show the exact permanent project-assets folder
            # for the selected analytics identity so the operator can verify that
            # this YouTube video points to the intended archived project.
            project_assets_dir = ANALYTICS_DIR / "project_assets" / str(retention_id)
            prod_prov = production_provenance(ANALYTICS_DB_PATH, retention_id)
            st.markdown("##### Retention mapping source")
            st.code(str(project_assets_dir.resolve()), language=None)
            st.caption(
                f"YouTube Video ID: {retention_rec.get('youtube_video_id') or 'N/A'} · "
                f"Analytics ID: {retention_id}"
            )
            if prod_prov.get("verified"):
                st.success(
                    f"Production provenance: VERIFIED · {prod_prov.get('scene_count', 0)} archived scene(s) · "
                    "production_timeline_snapshot.csv FOUND"
                )
            else:
                st.warning(
                    "Production provenance: UNVERIFIED — "
                    f"{prod_prov.get('reason') or 'canonical production snapshot unavailable'} "
                    "Visual Mode / Asset Type / Overlay Type are blocked from Production Learning."
                )

            scenes_now = scene_snapshot_df(ANALYTICS_DB_PATH, retention_id)

            if scenes_now.empty:
                st.warning(
                    "This video has no stored Actual Timeline or timestamped transcript. "
                    "Go to Timeline / Transcript first. Retention cannot be mapped without timestamps."
                )
            else:
                source_names = ", ".join(sorted(set(scenes_now["source"].dropna().astype(str))))
                st.success(
                    f"Content timeline available: {len(scenes_now)} segments · source: {source_names}"
                )

                retention_upload = st.file_uploader(
                    "Audience retention curve CSV",
                    type=["csv"],
                    key="retention_curve_upload",
                    help=(
                        "Needs retention % plus either video time/timestamp or video position %. "
                        "Average percentage viewed (%) alone is only a summary metric and will be rejected."
                    ),
                )

                if retention_upload is not None:
                    try:
                        retention_preview = pd.read_csv(retention_upload)
                        st.caption(
                            f"{len(retention_preview)} rows · columns: "
                            f"{', '.join(map(str, retention_preview.columns[:15]))}"
                        )
                        st.dataframe(retention_preview.head(20), width="stretch", hide_index=True)
                        retention_upload.seek(0)

                        if st.button("Import & Map Retention", type="primary", key="import_map_retention"):
                            retention_upload.seek(0)
                            retention_df = pd.read_csv(retention_upload)
                            result = import_retention_curve(
                                ANALYTICS_DB_PATH,
                                retention_id,
                                retention_df,
                                source_file=retention_upload.name,
                            )
                            st.success(
                                f"Imported {result['points']} retention points and mapped them to the stored timeline."
                            )
                            st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

                stored_points = retention_points_df(ANALYTICS_DB_PATH, retention_id)
                mapped = scene_retention_mapping(ANALYTICS_DB_PATH, retention_id)

                if not stored_points.empty:
                    st.markdown("#### Retention curve")
                    chart_df = stored_points[["time_sec","retention_percent"]].copy()
                    chart_df = chart_df.set_index("time_sec")
                    st.line_chart(chart_df)

                    st.caption(
                        f"{len(stored_points)} stored retention points · "
                        f"source file: {stored_points.iloc[-1].get('source_file') or '-'}"
                    )

                if not mapped.empty:
                    st.markdown("#### Scene-by-scene retention")
                    display = mapped.copy()
                    display["Start"] = display["start_sec"].map(
                        lambda x: f"{int(x)//60}:{int(x)%60:02d}"
                    )
                    display["End"] = display["end_sec"].map(
                        lambda x: f"{int(x)//60}:{int(x)%60:02d}"
                    )
                    for col in ["retention_start","retention_end","retention_avg","retention_delta"]:
                        display[col] = pd.to_numeric(display[col], errors="coerce").round(2)

                    cols = [
                        "scene_id","Start","End","retention_start","retention_end",
                        "retention_avg","retention_delta","retention_signal",
                        "visual_mode","asset_type","overlay_type","script_text"
                    ]
                    cols = [c for c in cols if c in display.columns]
                    st.dataframe(
                        display[cols].rename(columns={
                            "scene_id":"Scene",
                            "retention_start":"Start Retention %",
                            "retention_end":"End Retention %",
                            "retention_avg":"Avg Retention %",
                            "retention_delta":"Δ Retention",
                            "retention_signal":"Signal",
                            "visual_mode":"Visual Mode",
                            "asset_type":"Asset Type",
                            "overlay_type":"Overlay Type",
                            "script_text":"Script / Transcript",
                        }),
                        width="stretch",
                        hide_index=True,
                    )

                    # Persist and expose production-retention observations only when
                    # real production metadata exists for these actual-timeline scenes.
                    prod_evidence = production_learning_scene_df(ANALYTICS_DB_PATH, retention_id)
                    if not prod_prov.get("verified"):
                        st.info("Production Retention Learning blocked: no verified canonical production snapshot for this analytics_id.")
                    elif not prod_evidence.empty:
                        st.markdown("#### Production Retention Learning")
                        st.caption("Observed associations only — retention does not prove that a visual treatment caused the result. No ACTIVE production rule is created from a single video.")
                        pe = prod_evidence.copy()
                        for col in ["retention_start","retention_end","retention_avg","retention_delta"]:
                            if col in pe.columns:
                                pe[col] = pd.to_numeric(pe[col], errors="coerce").round(2)
                        show_cols = ["scene_id","asset_type","visual_mode","overlay_type","retention_start","retention_end","retention_delta","retention_signal","script_text"]
                        show_cols = [c for c in show_cols if c in pe.columns]
                        st.dataframe(pe[show_cols].rename(columns={
                            "scene_id":"Scene", "asset_type":"Asset Type", "visual_mode":"Visual Mode",
                            "overlay_type":"Overlay Type", "retention_start":"Start Retention %",
                            "retention_end":"End Retention %", "retention_delta":"Δ Retention",
                            "retention_signal":"Signal", "script_text":"Script / Transcript",
                        }), width="stretch", hide_index=True)

                        summary = production_learning_summary(ANALYTICS_DB_PATH, min_videos=1)
                        if not summary.empty:
                            st.markdown("##### Cross-video production evidence")
                            st.dataframe(summary, width="stretch", hide_index=True)
                            st.caption("Status is evidence maturity only: 1 video = OBSERVATION, 2 = REPEATED SIGNAL, 3+ = CHANNEL PATTERN CANDIDATE. This build does not activate production rules or override Production Mix.")

                    st.markdown("#### Script Retention Learning")
                    st.caption("Retention identifies WHERE viewers weakened; this section analyzes WHAT was being said. Visual/asset metadata is optional and is not required for old YouTube videos.")
                    learning = script_retention_learning(ANALYTICS_DB_PATH, retention_id, limit=12)
                    if learning.empty:
                        st.success("No meaningful script-level loss windows detected in the current mapped curve.")
                    else:
                        q = learning.copy()
                        q["Time Window"] = q.apply(lambda r: f"{int(r['start_sec'])//60}:{int(r['start_sec'])%60:02d}–{int(r['end_sec'])//60}:{int(r['end_sec'])%60:02d}", axis=1)
                        q["Retention"] = q.apply(lambda r: f"{r['retention_start']:.1f}% → {r['retention_end']:.1f}%", axis=1)
                        q["Drop"] = pd.to_numeric(q["retention_delta"], errors="coerce").round(2)
                        display_cols = ["Time Window","event","Retention","Drop","primary_issue","evidence","future_rule","script_text"]
                        st.dataframe(q[display_cols].rename(columns={
                            "event":"Event","primary_issue":"Primary Script Issue","evidence":"Why It Was Flagged",
                            "future_rule":"Future Script Rule","script_text":"Script / Transcript"
                        }), width="stretch", hide_index=True)
                        st.caption("Retention identifies WHERE viewers weakened; nearby transcript context suggests WHAT may have contributed. Specific causes are hypotheses, and unclear cases are labeled CAUSE UNCERTAIN rather than forced into a generic diagnosis. No fixed re-hook timer or per-N-second writing quota is prescribed.")
                        with st.expander("Diagnosis context (previous/current/next transcript)"):
                            ctx = q[["Time Window","context_text"]].rename(columns={"context_text":"Context Transcript"})
                            st.dataframe(ctx, width="stretch", hide_index=True)
                        st.warning("Script diagnoses are investigation hypotheses, not automatic causal claims. Promote a finding to a channel rule only after the same pattern repeats across multiple learning-eligible videos.")

                    with st.expander("Raw scene-by-scene retention (diagnostic)"):
                        drops = retention_drop_summary(ANALYTICS_DB_PATH, retention_id, limit=10)
                        if drops.empty:
                            st.info("No raw drop/weak-hold rows detected.")
                        else:
                            d = drops.copy()
                            d["Time"] = d["start_sec"].map(lambda x: f"{int(x)//60}:{int(x)%60:02d}")
                            d["Drop"] = pd.to_numeric(d["retention_delta"], errors="coerce").round(2)
                            d["Avg Retention %"] = pd.to_numeric(d["retention_avg"], errors="coerce").round(2)
                            cols = ["scene_id","Time","Drop","Avg Retention %","retention_signal","script_text"]
                            st.dataframe(d[cols].rename(columns={"scene_id":"Scene","retention_signal":"Signal","script_text":"Script / Transcript"}), width="stretch", hide_index=True)
                elif not scenes_now.empty:
                    st.info(
                        "No stored YouTube API retention curve is available for this video yet. Run Sync YouTube Analytics first; "
                        "the CSV uploader above is only a manual fallback if YouTube does not provide retention data."
                    )

    with tabs[3]:
        st.markdown("### Channel-Wide Content / Performance Import")
        st.caption(
            "Core improvement workflow: upload channel-wide YouTube Studio Content/Performance CSV files. "
            "Videos are matched by Video ID first. Draft projects can also be reconciled conservatively "
            "when the public YouTube title changed, using title similarity plus available duration/date evidence. "
            "Ambiguous matches remain YouTube-only for one-time manual attach. Traffic Source is intentionally excluded for now."
        )

        bulk_content_files = st.file_uploader(
            "Upload Content / Performance CSV file(s)",
            type=["csv"],
            accept_multiple_files=True,
            key="analytics_bulk_content",
            help="You can select one or several Content/Performance exports together.",
        )
        date_label = st.text_input(
            "Snapshot/date-range label (optional)",
            placeholder="e.g. Since published export 2026-08-27",
            key="analytics_bulk_snapshot_label",
        )

        if bulk_content_files:
            st.caption(f"{len(bulk_content_files)} file(s) selected.")
            for item in bulk_content_files:
                try:
                    preview_df = pd.read_csv(item)
                    st.markdown(f"**{item.name}**")
                    st.caption(f"{len(preview_df)} rows · columns: {', '.join(map(str, preview_df.columns[:12]))}")
                    st.dataframe(preview_df.head(10), width="stretch", hide_index=True)
                    item.seek(0)
                except Exception as exc:
                    st.error(f"{item.name}: {exc}")

            if st.button("Import All Content / Performance Files", type="primary", key="import_bulk_content"):
                total_imported = 0
                total_skipped = 0
                all_errors = []
                for item in bulk_content_files:
                    try:
                        item.seek(0)
                        df = pd.read_csv(item)
                        normalized_cols = {
                            re.sub(r"[^a-z0-9]+", "", str(c).lower())
                            for c in df.columns
                        }
                        if "trafficsource" in normalized_cols or "trafficsourcetype" in normalized_cols:
                            raise AnalyticsDBError(
                                "Traffic Source report detected. Traffic Source is disabled in the current analytics workflow."
                            )
                        result = bulk_import_channel_content_csv(
                            ANALYTICS_DB_PATH,
                            df,
                            source_file=item.name,
                            snapshot_label=date_label.strip(),
                        )
                        total_imported += int(result.get("imported_videos", 0))
                        total_skipped += int(result.get("skipped_rows", 0))
                        all_errors.extend([f"{item.name}: {e}" for e in result.get("errors", [])])
                        st.success(f"{item.name}: {result.get('imported_videos', 0)} video(s) imported.")
                    except Exception as exc:
                        all_errors.append(f"{item.name}: {exc}")
                        st.error(f"{item.name}: {exc}")

                if total_imported:
                    st.success(
                        f"Content/Performance update complete: {total_imported} video row(s) imported "
                        f"across {len(bulk_content_files)} file(s)."
                    )
                if total_skipped:
                    st.caption(f"{total_skipped} aggregate/empty row(s) skipped.")
                if all_errors:
                    with st.expander("Import warnings / errors"):
                        for err in all_errors:
                            st.write(f"• {err}")

        st.markdown("#### One-time data — do not upload again")
        st.write(
            "• Actual Timeline snapshots already stored in the permanent DB\n"
            "• Timestamped transcripts already stored for deleted/legacy projects\n"
            "• Project links already discovered by Auto-Link\n"
            "• YouTube Video ID once linked"
        )
        st.caption(
            "Your recurring analytics update is now Content/Performance only. "
            "Traffic Source data is not used by the current improvement engine."
        )

        # One-time fallback for a changed public title when automatic reconciliation
        # deliberately refuses an ambiguous match. Keep the project's permanent
        # analytics_id so its archived script/timeline remains attached.
        current_registry = list_videos(ANALYTICS_DB_PATH)
        unlinked_projects = [
            v for v in current_registry
            if v.get("project_id") and not str(v.get("youtube_video_id") or "").strip()
        ]
        youtube_only = [
            v for v in current_registry
            if v.get("source_type") == "youtube_only" and str(v.get("youtube_video_id") or "").strip()
        ]
        if unlinked_projects and youtube_only:
            with st.expander("Manual fallback — attach changed-title YouTube video to project"):
                st.caption(
                    "Use this only when the imported YouTube title changed enough that automatic matching stayed ambiguous. "
                    "The project's permanent Analytics ID, saved script, and saved timeline are preserved."
                )
                project_ids = [v["analytics_id"] for v in unlinked_projects]
                youtube_ids = [v["analytics_id"] for v in youtube_only]
                project_labels = {
                    v["analytics_id"]: f"{v.get('locked_title') or v.get('project_slug') or v['analytics_id']} · project"
                    for v in unlinked_projects
                }
                youtube_labels = {
                    v["analytics_id"]: f"{v.get('youtube_title') or v['analytics_id']} · {v.get('youtube_video_id') or ''}"
                    for v in youtube_only
                }
                project_choice = st.selectbox(
                    "Existing project", project_ids, format_func=lambda x: project_labels[x],
                    key="analytics_manual_link_project",
                )
                youtube_choice = st.selectbox(
                    "Imported YouTube video", youtube_ids, format_func=lambda x: youtube_labels[x],
                    key="analytics_manual_link_youtube",
                )
                if st.button("Attach YouTube video to this project", key="analytics_manual_link_confirm"):
                    try:
                        link_youtube_record_to_project(
                            ANALYTICS_DB_PATH, project_choice, youtube_choice
                        )
                        st.success(
                            "Linked permanently. Future imports will use the YouTube Video ID, and the project's saved timeline/script remain attached."
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))


    videos = [
        v for v in list_videos(ANALYTICS_DB_PATH)
        if str(v.get("youtube_video_id") or "").strip()
    ]

    with tabs[4]:
        st.markdown("### Video Registry")
        st.caption(
            "Only records with a YouTube Video ID are shown here. Local projects remain hidden from Analytics until a Video ID is linked."
        )
        if not videos:
            st.info("No YouTube-linked videos yet.")
        else:
            registry_rows = []
            for v in videos:
                registry_rows.append({
                    "Title": v.get("display_title") or v.get("youtube_title") or v.get("locked_title") or "",
                    "Video ID": v.get("youtube_video_id") or "",
                    "Source": v.get("source_type") or "",
                    "Project Folder": v.get("project_folder_status") or "",
                    "Timeline": v.get("timeline_status") or "",
                    "Analytics": v.get("analytics_status") or "",
                    "Created": v.get("created_at") or "",
                    "Analytics ID": v.get("analytics_id") or "",
                })
            st.caption(f"{len(registry_rows)} permanent video record(s) with YouTube IDs.")
            st.dataframe(pd.DataFrame(registry_rows), width="stretch", hide_index=True)

    with tabs[5]:
        st.markdown("### YouTube Video Link")
        st.caption(
            "This does not upload anything to YouTube. Select the local project, paste the permanent YouTube Video ID, "
            "and the app binds that ID to the project's existing Analytics ID. Titles are not used for identity matching."
        )
        all_records = list_videos(ANALYTICS_DB_PATH)
        link_projects = [v for v in all_records if v.get("project_id") and not str(v.get("youtube_video_id") or "").strip()]
        if not link_projects:
            st.info("No unlinked local projects are waiting for a YouTube Video ID.")
        else:
            link_ids = [v["analytics_id"] for v in link_projects]
            link_labels = {
                v["analytics_id"]: f"{v.get('locked_title') or v.get('project_slug') or v['analytics_id']} · {v['analytics_id']}"
                for v in link_projects
            }
            project_choice = st.selectbox("Project", link_ids, format_func=lambda x: link_labels[x], key="youtube_video_link_project")
            assets_path = ANALYTICS_DIR / "project_assets" / str(project_choice)
            st.write(f"**Analytics ID:** `{project_choice}`")
            st.write("**Project assets:**")
            st.code(str(assets_path.resolve()), language=None)
            if assets_path.is_dir():
                st.caption("Project assets folder: FOUND")
            else:
                st.warning("Project assets folder: MISSING")
            video_id_input = st.text_input("YouTube Video ID", key="youtube_video_link_id", placeholder="e.g. RItFbOZinFA")
            st.caption("Paste the Video ID only. This creates the permanent youtube_video_id ↔ analytics_id binding.")
            if st.button("Link YouTube Video ID", type="primary", key="youtube_video_link_confirm"):
                try:
                    bound = bind_youtube_video_id_to_project(ANALYTICS_DB_PATH, project_choice, video_id_input)
                    st.success(f"VERIFIED LINK saved: {video_id_input.strip()} ↔ {bound}")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    with tabs[6]:
        st.markdown("### Thumbnail Learning")
        st.caption(
            "No six-stage workflow is required. Every YouTube Analytics sync automatically checks each current thumbnail by permanent Video ID, "
            "archives only new/changed artwork, extracts thumbnail text + visual packaging, joins eligible CTR/impressions evidence, "
            "refreshes channel comparisons, and updates candidate packaging rules. Unchanged thumbnails are hash-skipped to avoid repeat vision cost."
        )

        inventory = thumbnail_inventory_df(ANALYTICS_DB_PATH)
        analyses = thumbnail_analysis_df(ANALYTICS_DB_PATH)
        evidence_all = thumbnail_ctr_evidence_df(ANALYTICS_DB_PATH)
        packaging_rules = all_channel_packaging_rules(ANALYTICS_DB_PATH)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Current thumbnails", 0 if inventory.empty else len(inventory))
        m2.metric("Analyzed", 0 if analyses.empty else int(analyses["analytics_id"].nunique()))
        m3.metric("CTR joined", 0 if evidence_all.empty else int(evidence_all["analytics_id"].nunique()))
        m4.metric("ACTIVE rules", 0 if packaging_rules.empty else int((packaging_rules["status"] == "ACTIVE").sum()))

        if not analyses.empty:
            st.markdown("#### Extracted Thumbnail Text + Packaging")
            text_cols = [
                c for c in [
                    "title_at_analysis", "thumbnail_text", "text_word_count", "text_line_count",
                    "question_hook", "number_hook", "title_thumbnail_relationship", "hero_category",
                    "presenter_present", "arrow_present", "visual_complexity", "analyzed_at"
                ] if c in analyses.columns
            ]
            st.dataframe(analyses[text_cols], width="stretch", hide_index=True)
        else:
            st.info("Run Sync YouTube Analytics. Thumbnail text and visual analysis will appear here automatically.")

        st.markdown("#### Channel Packaging Learnings")
        st.caption(
            "Candidate evidence is created automatically. Only promotion to ACTIVE remains a deliberate review action so one noisy association cannot silently steer future thumbnails."
        )
        if packaging_rules.empty:
            st.info("No packaging-rule candidates yet. They will appear automatically when enough CTR + impression evidence exists.")
        else:
            # Review candidates by evidence strength instead of forcing the user through one long flat list.
            # This is display-only classification: it never changes promotion thresholds or rule status.
            def _packaging_family(feature_name: str) -> str:
                name = str(feature_name or "").lower()
                if name.startswith("text_") or name in {"question_hook", "number_hook", "title_thumbnail_relationship"}:
                    return "Text & title pairing"
                if "color" in name or "palette" in name or "brightness" in name or "contrast" in name or "temperature" in name:
                    return "Colors & contrast"
                if name.startswith("presenter_"):
                    return "Presenter"
                if name.startswith("hero_") or name in {"arrow_present", "circle_present", "visual_complexity"}:
                    return "Hero & visual cues"
                if "position" in name or "layout" in name or "composition" in name or "focal" in name:
                    return "Layout & composition"
                return "Other packaging"

            review_rows = []
            for _, r in packaging_rules.iterrows():
                audit_row = packaging_rule_promotion_audit(ANALYTICS_DB_PATH, str(r['rule_key']))
                delta = float(r.get('ctr_delta_points') or 0.0)
                status = str(r.get('status') or '')
                if status == 'ACTIVE':
                    evidence_group = "ACTIVE"
                elif status in {'REJECTED', 'RETIRED'}:
                    evidence_group = status
                elif bool(audit_row.get('promotion_ready')):
                    evidence_group = "Strong Positive" if delta > 0 else "Strong Negative"
                else:
                    evidence_group = "Not Enough Evidence"
                review_rows.append({
                    **r.to_dict(),
                    'evidence_group': evidence_group,
                    'rule_family': _packaging_family(r.get('feature_name')),
                    'promotion_ready': bool(audit_row.get('promotion_ready')),
                    'ci_low': audit_row.get('delta_ci95_low'),
                    'ci_high': audit_row.get('delta_ci95_high'),
                })
            review_df = pd.DataFrame(review_rows)

            # Consolidate correlated micro-signals for review. This does NOT merge evidence,
            # add CTR deltas, or auto-promote anything; it simply prevents the UI from
            # presenting overlapping measurements of the same packaging idea as independent
            # discoveries. The strongest promotion-eligible row remains the representative.
            def _signal_cluster(feature_name: str) -> str:
                name = str(feature_name or "").lower()
                if name in {"text_word_count", "text_length_bucket", "text_line_count", "text_density_bucket"}:
                    return "Text amount & hierarchy"
                if name in {"question_hook", "number_hook"}:
                    return "Text hook style"
                if name == "title_thumbnail_relationship":
                    return "Title-thumbnail relationship"
                if name in {"background_color_family", "dominant_palette", "text_color_scheme", "accent_color_family", "palette_temperature", "contrast_level", "background_brightness"}:
                    return "Color & contrast system"
                if name in {"presenter_present", "presenter_position", "presenter_size", "expression", "gaze_target"}:
                    return "Presenter treatment"
                if name in {"hero_subject", "hero_count", "arrow_present", "arrow_target", "major_visual_object_count"}:
                    return "Hero & attention cues"
                if name in {"composition_layout", "visual_complexity", "subject_separation", "background_style"}:
                    return "Composition & separation"
                return _packaging_family(feature_name)

            review_df['signal_cluster'] = review_df['feature_name'].map(_signal_cluster)

            strong_mask = review_df['evidence_group'].isin(['Strong Positive', 'Strong Negative'])
            cluster_source = review_df[strong_mask].copy()
            if not cluster_source.empty:
                cluster_source['abs_delta'] = pd.to_numeric(cluster_source['ctr_delta_points'], errors='coerce').abs().fillna(0.0)
                cluster_source = cluster_source.sort_values(
                    ['evidence_group','context_type','context_value','signal_cluster','promotion_ready','abs_delta','total_impressions'],
                    ascending=[True,True,True,True,False,False,False]
                )
                cluster_rows = []
                for (grp, context_type, context_value, cluster), part in cluster_source.groupby(['evidence_group','context_type','context_value','signal_cluster'], sort=False):
                    rep = part.iloc[0]
                    support = part[part['rule_key'] != rep['rule_key']]
                    examples = [f"{r.feature_name}={r.feature_value}" for r in support.head(4).itertuples()]
                    cluster_rows.append({
                        'evidence_group': grp,
                        'signal_cluster': cluster,
                        'context_type': context_type,
                        'context_value': context_value,
                        'representative_rule_key': str(rep['rule_key']),
                        'supporting_rule_keys': [str(x) for x in support['rule_key'].tolist()],
                        'representative_signal': f"{rep['feature_name']}={rep['feature_value']}",
                        'representative_videos': int(rep['videos']),
                        'representative_impressions': float(rep['total_impressions']),
                        'representative_ctr_delta': float(rep['ctr_delta_points']),
                        'supporting_signals': int(len(support)),
                        'support_examples': ' · '.join(examples),
                    })
                cluster_df = pd.DataFrame(cluster_rows)
            else:
                cluster_df = pd.DataFrame()

            active_n = int((review_df['evidence_group'] == 'ACTIVE').sum())
            pos_n = int((review_df['evidence_group'] == 'Strong Positive').sum())
            neg_n = int((review_df['evidence_group'] == 'Strong Negative').sum())
            weak_n = int((review_df['evidence_group'] == 'Not Enough Evidence').sum())
            q1, q2, q3, q4 = st.columns(4)
            q1.metric("ACTIVE", active_n)
            q2.metric("Strong positive", pos_n)
            q3.metric("Strong negative", neg_n)
            q4.metric("Need more evidence", weak_n)

            group_options = [g for g in ["ACTIVE", "Strong Positive", "Strong Negative", "Not Enough Evidence", "REJECTED", "RETIRED"] if g in set(review_df['evidence_group'])]
            chosen_group = st.selectbox("Evidence group", group_options, key="thumbnail_rule_evidence_group")

            if chosen_group in {'Strong Positive', 'Strong Negative'} and not cluster_df.empty:
                visible_clusters = cluster_df[cluster_df['evidence_group'] == chosen_group].copy()
                if not visible_clusters.empty:
                    st.markdown("##### Consolidated signal clusters")
                    st.caption(
                        "Correlated measurements are grouped so word count, line count and text density are not mistaken for separate independent discoveries. "
                        "CTR deltas are never added together. The representative is simply the strongest eligible signal in that cluster; supporting rows remain visible below."
                    )
                    st.dataframe(
                        visible_clusters[["signal_cluster","context_type","context_value","representative_signal","representative_videos","representative_impressions","representative_ctr_delta","supporting_signals","support_examples"]],
                        width="stretch", hide_index=True
                    )
                    cluster_labels = {
                        f"{r['signal_cluster']} · {r['context_type']}/{r['context_value']} · {r['representative_signal']} · {int(r['representative_videos'])} videos · ΔCTR {float(r['representative_ctr_delta']):+.2f}": idx
                        for idx, r in visible_clusters.iterrows()
                    }
                    selected_cluster_label = st.selectbox("Cluster review", list(cluster_labels), key="thumbnail_cluster_review")
                    selected_cluster = visible_clusters.loc[cluster_labels[selected_cluster_label]]
                    st.caption(
                        "Promoting a cluster creates ONE ACTIVE guidance rule. Supporting micro-signals stay evidence only; "
                        "their CTR deltas are not added and they are not injected as separate instructions."
                    )
                    cluster_note = st.text_input("Cluster review note (optional)", key="thumbnail_cluster_note")
                    if st.button("Promote cluster to ACTIVE", key="thumbnail_cluster_activate"):
                        try:
                            promote_packaging_signal_cluster(
                                ANALYTICS_DB_PATH,
                                str(selected_cluster['signal_cluster']),
                                str(selected_cluster['representative_rule_key']),
                                list(selected_cluster['supporting_rule_keys']),
                                cluster_note,
                            )
                            write_active_packaging_rules_file(ANALYTICS_DB_PATH, ACTIVE_CHANNEL_PACKAGING_RULES_PATH)
                            st.success("Correlated packaging cluster promoted as one ACTIVE guidance rule.")
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))

            grouped = review_df[review_df['evidence_group'] == chosen_group].copy()
            family_options = ["All"] + sorted(grouped['rule_family'].dropna().unique().tolist())
            chosen_family = st.selectbox("Rule family", family_options, key="thumbnail_rule_family")
            if chosen_family != "All":
                grouped = grouped[grouped['rule_family'] == chosen_family]
            grouped = grouped.sort_values(['promotion_ready','ctr_delta_points','total_impressions'], ascending=[False, False, False])

            st.dataframe(
                grouped[[c for c in ["evidence_group","rule_family","feature_name","feature_value","videos","total_impressions","ctr_delta_points","ci_low","ci_high","attribution_status"] if c in grouped.columns]],
                width="stretch", hide_index=True
            )

            rule_labels = {
                f"{r['evidence_group']} · {r['rule_family']} · {r['feature_name']}={r['feature_value']} · {int(r['videos'])} videos · ΔCTR {float(r['ctr_delta_points']):+.2f}": r['rule_key']
                for _, r in grouped.iterrows()
            }
            selected_rule_label = st.selectbox("Packaging rule review", list(rule_labels), key="thumbnail_auto_rule_review")
            selected_rule_key = rule_labels[selected_rule_label]
            selected_rule = packaging_rules[packaging_rules['rule_key'] == selected_rule_key].iloc[0]
            st.write(str(selected_rule['guidance_text']))
            st.caption(
                f"Evidence: {int(selected_rule['videos'])} videos · {float(selected_rule['total_impressions']):,.0f} impressions · "
                f"CTR delta {float(selected_rule['ctr_delta_points']):+.2f} points"
            )
            audit = packaging_rule_promotion_audit(ANALYTICS_DB_PATH, selected_rule_key)
            promotion_ready = bool(audit.get('promotion_ready'))
            lo, hi = audit.get('delta_ci95_low'), audit.get('delta_ci95_high')
            if lo is not None and hi is not None:
                st.caption(f"Approx. 95% CTR-delta interval: {float(lo):+.2f} to {float(hi):+.2f} percentage points.")
            if promotion_ready:
                st.success("PROMOTION-ELIGIBLE — evidence gate passed. This remains observational channel evidence, not causal proof.")
            elif str(selected_rule.get('status')) == 'CANDIDATE':
                st.warning("Keep as CANDIDATE — " + " ".join(audit.get('reasons') or ['comparison evidence is not yet sufficient.']))
            review_note = st.text_input("Review note (optional)", key="thumbnail_auto_rule_note")
            c1, c2, c3 = st.columns(3)
            if c1.button("Promote to ACTIVE", key="thumbnail_auto_activate", disabled=not promotion_ready):
                try:
                    set_packaging_rule_status(ANALYTICS_DB_PATH, selected_rule_key, "ACTIVE", review_note)
                    write_active_packaging_rules_file(ANALYTICS_DB_PATH, ACTIVE_CHANNEL_PACKAGING_RULES_PATH)
                    st.success("Packaging guidance promoted to ACTIVE.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            if c2.button("Reject", key="thumbnail_auto_reject"):
                set_packaging_rule_status(ANALYTICS_DB_PATH, selected_rule_key, "REJECTED", review_note)
                write_active_packaging_rules_file(ANALYTICS_DB_PATH, ACTIVE_CHANNEL_PACKAGING_RULES_PATH)
                st.rerun()
            if c3.button("Retire", key="thumbnail_auto_retire"):
                set_packaging_rule_status(ANALYTICS_DB_PATH, selected_rule_key, "RETIRED", review_note)
                write_active_packaging_rules_file(ANALYTICS_DB_PATH, ACTIVE_CHANNEL_PACKAGING_RULES_PATH)
                st.rerun()

            with st.expander("All packaging rules (raw)"):
                st.dataframe(
                    packaging_rules[["status","context_type","context_value","feature_name","feature_value","videos","total_impressions","ctr_delta_points","attribution_status"]],
                    width="stretch", hide_index=True
                )

        if not inventory.empty:
            with st.expander("Thumbnail archive diagnostics"):
                show = inventory.rename(columns={
                    "title":"Title", "youtube_video_id":"Video ID", "downloaded_at":"Downloaded",
                    "source_variant":"Source", "width":"Width", "height":"Height",
                    "analysis_status":"Analysis", "analytics_id":"Analytics ID",
                })
                st.dataframe(show[["Title","Video ID","Downloaded","Source","Width","Height","Analysis","Analytics ID"]], width="stretch", hide_index=True)

    if not videos:
        with tabs[7]:
            st.info("No YouTube-linked videos yet.")
        with tabs[8]:
            st.info("No YouTube-linked videos yet.")
        with tabs[9]:
            st.info("No YouTube-linked videos yet.")
        return

    labels = {
        v["analytics_id"]: f"{v.get('display_title') or v['analytics_id']} · {v.get('youtube_video_id') or 'no video id'}"
        for v in videos
    }
    ids = list(labels)



    with tabs[7]:
        st.markdown("### Import YouTube Studio CSVs")
        selected_id = st.selectbox("Video", ids, format_func=lambda x: labels[x], key="analytics_import_video")
        st.caption(
            "Performance/Content CSV only. Traffic Source reports are disabled for now. "
            "Missing metrics stay NULL—not zero."
        )
        uploaded = st.file_uploader(
            "Upload one or more YouTube Studio CSV files",
            type=["csv"],
            accept_multiple_files=True,
            key="analytics_csv_imports",
        )
        if uploaded and st.button("Import selected CSV files", type="primary"):
            results = []
            for item in uploaded:
                try:
                    df = pd.read_csv(item)
                    normalized_cols = {
                        re.sub(r"[^a-z0-9]+", "", str(c).lower())
                        for c in df.columns
                    }
                    if "trafficsource" in normalized_cols or "trafficsourcetype" in normalized_cols:
                        raise AnalyticsDBError(
                            "Traffic Source report detected. Traffic Source is disabled for now."
                        )
                    result = import_youtube_csv(
                        ANALYTICS_DB_PATH,
                        selected_id,
                        df,
                        source_file=item.name,
                    )
                    if result.get("kind") != "performance":
                        raise AnalyticsDBError(
                            "Only Content/Performance report data is accepted in the current workflow."
                        )
                    results.append((item.name, result))
                    st.success(f"{item.name}: performance · {result['rows']} row(s) imported")
                except Exception as exc:
                    st.error(f"{item.name}: {exc}")
            if results:
                st.caption("Data is now stored independently of the project folder.")

        st.markdown("#### Link / update YouTube identity")
        rec = get_video(ANALYTICS_DB_PATH, selected_id) or {}
        with st.form("analytics_identity_form"):
            yt_title = st.text_input("YouTube title", value=str(rec.get("youtube_title") or rec.get("locked_title") or ""))
            yt_id = st.text_input("YouTube Video ID", value=str(rec.get("youtube_video_id") or ""))
            pub = st.text_input("Publish date", value=str(rec.get("publish_date") or ""), placeholder="YYYY-MM-DD")
            save_identity = st.form_submit_button("Save identity")
        if save_identity:
            try:
                update_video_identity(
                    ANALYTICS_DB_PATH,
                    selected_id,
                    youtube_title=yt_title,
                    youtube_video_id=yt_id,
                    publish_date=pub,
                )
                st.success("YouTube identity updated.")
            except Exception as exc:
                st.error(str(exc))

    with tabs[8]:
        st.markdown("### Timeline / Transcript Fallback")
        selected_id = st.selectbox("Video", ids, format_func=lambda x: labels[x], key="analytics_timeline_video")
        rec = get_video(ANALYTICS_DB_PATH, selected_id) or {}
        st.write(
            f"Current source: **{rec.get('timeline_source') or rec.get('timeline_status') or 'pending'}** · "
            f"Project folder: **{rec.get('project_folder_status')}**"
        )

        # If this record still points to a live local project, offer manual re-snapshot.
        p = Path(str(rec.get("project_path_at_creation") or ""))
        actual = p / "08_actual_timeline.csv" if str(p) else None
        if actual and actual.is_file():
            st.success("08_actual_timeline.csv is available.")
            if st.button("Refresh permanent Actual Timeline snapshot", key="analytics_refresh_timeline"):
                try:
                    count = snapshot_actual_timeline(
                        ANALYTICS_DB_PATH,
                        selected_id,
                        actual,
                        production_sheet_path=p / "07_production_sheet.csv",
                    )
                    st.success(f"Saved {count} actual timeline scenes permanently.")
                except Exception as exc:
                    st.error(str(exc))
        else:
            if needs_transcript_upload(ANALYTICS_DB_PATH, selected_id):
                st.warning(
                    "Actual Timeline is not available and no transcript snapshot is stored yet. "
                    "Upload this video's timestamped transcript once to preserve content-level analytics."
                )
            else:
                st.success(
                    "No Actual Timeline is available, but a transcript snapshot is already stored. "
                    "You do not need to upload the transcript again."
                )

        if needs_transcript_upload(ANALYTICS_DB_PATH, selected_id):
            transcript_file = st.file_uploader(
                "Timestamped transcript (.txt)",
                type=["txt"],
                key="analytics_transcript_upload",
                help="Expected format: [00:00:00] text ... then [00:00:03] next text ...",
            )
            if transcript_file is not None:
                transcript_text = transcript_file.getvalue().decode("utf-8", errors="replace")
                st.text_area("Transcript preview", transcript_text[:5000], height=220, disabled=True)
                if st.button("Save transcript-based analysis timeline", type="primary"):
                    try:
                        count = snapshot_timestamped_transcript(ANALYTICS_DB_PATH, selected_id, transcript_text)
                        st.success(
                            f"Saved {count} transcript segments as TS0001...TS{count:04d}. "
                            "These are marked transcript_reconstructed, not original production scenes. "
                            "This transcript will not be requested again for this analytics record."
                        )
                    except Exception as exc:
                        st.error(str(exc))

        scene_df = scene_snapshot_df(ANALYTICS_DB_PATH, selected_id)
        if not scene_df.empty:
            st.markdown("#### Permanent content snapshot")
            st.dataframe(scene_df.head(300), width="stretch", hide_index=True)
            st.caption(f"{len(scene_df)} stored content segments. These remain after the local project folder is deleted.")

    with tabs[9]:
        st.markdown("### Video Detail")
        selected_id = st.selectbox("Video", ids, format_func=lambda x: labels[x], key="analytics_detail_video")
        rec = get_video(ANALYTICS_DB_PATH, selected_id) or {}
        perf = latest_performance(ANALYTICS_DB_PATH, selected_id)
        st.json({
            "title": rec.get("youtube_title") or rec.get("locked_title"),
            "video_id": rec.get("youtube_video_id"),
            "publish_date": rec.get("publish_date"),
            "publish_day": rec.get("publish_weekday"),
            "source_type": rec.get("source_type"),
            "project_folder_status": rec.get("project_folder_status"),
            "timeline_source": rec.get("timeline_source"),
            "analytics_status": rec.get("analytics_status"),
            "retention_status": rec.get("retention_status"),
            "comments_status": rec.get("comments_status"),
        })
        if perf:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Views", "-" if perf.get("views") is None else f"{perf['views']:,.0f}")
            c2.metric("CTR", "-" if perf.get("ctr_percent") is None else f"{perf['ctr_percent']:.2f}%")
            avd = perf.get("average_view_duration_seconds")
            if avd is None:
                avd_label = "-"
            else:
                avd_label = f"{int(avd)//60}:{int(avd)%60:02d}"
            c3.metric("AVD", avd_label)
            c4.metric(
                "Avg % Viewed",
                "-" if perf.get("average_percentage_viewed") is None else f"{perf['average_percentage_viewed']:.2f}%"
            )
            st.caption(f"Latest performance import: {perf.get('imported_at')} · {perf.get('source_file')}")
        else:
            st.info("No performance CSV imported yet.")

        st.markdown("#### Publish Day Performance")
        weekday_df = weekday_performance_summary(ANALYTICS_DB_PATH)
        if weekday_df.empty:
            st.info("No YouTube publish dates are stored yet. Re-import Content/Performance CSV to populate them.")
        else:
            show = weekday_df.copy()
            show["AVD"] = show["avg_avd_seconds"].map(
                lambda x: "-" if pd.isna(x) else f"{int(round(x))//60}:{int(round(x))%60:02d}"
            )
            show = show.rename(columns={
                "weekday": "Publish Day",
                "videos": "Videos",
                "avg_views": "Avg Views",
                "avg_impressions": "Avg Impressions",
                "avg_ctr": "Avg CTR %",
                "avg_apv": "Avg % Viewed",
                "avg_watch_hours": "Avg Watch Hours",
                "avg_subscribers": "Avg Subscribers",
            })
            cols = ["Publish Day","Videos","Avg CTR %","Avg % Viewed","AVD","Avg Views","Avg Impressions","Avg Watch Hours","Avg Subscribers"]
            st.dataframe(show[cols], width="stretch", hide_index=True)

            eligible = show[show["Videos"] >= 2].copy()
            eligible = eligible[
                eligible["Avg CTR %"].notna() & eligible["Avg % Viewed"].notna()
            ].copy()
            if not eligible.empty:
                eligible["_ctr_rank"] = eligible["Avg CTR %"].rank(pct=True)
                eligible["_apv_rank"] = eligible["Avg % Viewed"].rank(pct=True)
                eligible["_score"] = eligible["_ctr_rank"] * 0.5 + eligible["_apv_rank"] * 0.5
                best = eligible.sort_values("_score", ascending=False).iloc[0]
                st.success(
                    f"Current best publish-day signal: {best['Publish Day']} "
                    f"(CTR + Average % Viewed; {int(best['Videos'])} videos in sample)."
                )
            elif show["Avg CTR %"].isna().all():
                st.warning(
                    "Publish-day winner is not calculated because CTR is missing. "
                    "Import a Content/Performance CSV containing Thumbnail click-through rate (%)."
                )
            else:
                st.caption(
                    "Best-day recommendation waits until a weekday has at least 2 videos "
                    "with both CTR and Average % Viewed."
                )


def main() -> None:
    st.set_page_config(page_title=f"Senior Health AI V{system_version()}", page_icon="🎬", layout="wide")
    inject_css()
    st.title(f"Senior Health AI V{system_version()}")
    st.caption("Auto Revision Engine · QA Dashboard · Production Cleaner · Production Lock 2.0 · Direct Codex Run")
    pages = ["Dashboard", "New Project", "Workflow", "Writer Workspace", "Retention Structure Analysis", "Narrative QA", "Medical Gate 2", "Speech Optimizer", "QA Dashboard", "Production Lock", "Production", "Opus Image Prompt Import", "Image Generation", "Text Overlay Import", "Files", "Analytics", "Config"]
    page = st.sidebar.radio("Navigation", pages)
    handlers = {
        "Dashboard": render_dashboard, "New Project": render_new_project, "Workflow": render_workflow,
        "Writer Workspace": render_writer_workspace, "Retention Structure Analysis": render_retention_structure_analysis, "Narrative QA": render_narrative_qa, "Medical Gate 2": render_medical_gate_2,
        "Speech Optimizer": render_speech_optimizer, "QA Dashboard": render_qa_dashboard, "Production Lock": render_production_lock,
        "Production": render_production, "Opus Image Prompt Import": render_opus_image_prompt_import, "Image Generation": render_images, "Text Overlay Import": render_text_overlay_import, "Files": render_files,
        "Analytics": render_analytics, "Config": render_config,
    }
    handlers[page]()


if __name__ == "__main__":
    main()

from __future__ import annotations
import os
from pathlib import Path
import streamlit as st

# Backward-compatible pure settings-page renderer retained for the existing
# dashboard contract test. The operational UI below is Streamlit.
def _page(message: str = "") -> bytes:
    from Thumbnail_Pipeline.dashboard.settings import get_dashboard_settings
    s=get_dashboard_settings()
    notice=f"<p>{message}</p>" if message else ""
    return f"""<!doctype html><html><body>{notice}<form>
<input name="min_impressions" value="{s['min_impressions']}">
<input name="full_reliability_impressions" value="{s['full_reliability_impressions']}">
<button>Save Settings</button>
<p>Source of truth: {s['source']}</p>
</form></body></html>""".encode("utf-8")

from Thumbnail_Pipeline.runner.__main__ import build_project_prompt_state, resolve_project
from Thumbnail_Pipeline.qa import evaluate_generation_gate
from Thumbnail_Pipeline.prompt_export import export_final_thumbnail_prompt
from Thumbnail_Pipeline.adapters.v2_youtube_api import V2YouTubeReferenceProvider, access_token_from_v2_files_read_only
from Thumbnail_Pipeline.adapters.youtube_thumbnail_analysis import openai_thumbnail_text_analyzer
from Thumbnail_Pipeline.dashboard.settings import get_dashboard_settings, save_dashboard_settings

st.set_page_config(page_title="Thumbnail Pipeline", page_icon="🖼️", layout="wide")
st.title("Thumbnail Pipeline")
st.caption("Project → analytics → YouTube references → intelligence → composition → final prompt. No image generation, YouTube upload, or V2 write.")

projects_root=Path("Projects")
projects=sorted(p.name for p in projects_root.iterdir() if p.is_dir() and (p/"project.json").is_file()) if projects_root.is_dir() else []

tab_run,tab_refs,tab_evidence,tab_settings=st.tabs(["Run Pipeline","YouTube References","Evidence & Audit","Settings"])

with tab_run:
    if not projects:
        st.error("No project folders with project.json found under Projects/.")
        st.stop()
    left,right=st.columns([2,1])
    with left:
        project_name=st.selectbox("Project",projects)
    with right:
        use_youtube=st.checkbox("Analyze YouTube references",value=True)
    with st.expander("Connections",expanded=False):
        client_json=st.text_input("YouTube OAuth client JSON",value="Analytics/youtube_oauth_credentials.json")
        token_json=st.text_input("YouTube OAuth token JSON",value="Analytics/youtube_oauth_token.json")
        vision_key=st.text_input("OpenAI vision key (optional)",value=os.environ.get("OPENAI_API_KEY",""),type="password")
        vision_model=st.text_input("Vision model",value=os.environ.get("THUMBNAIL_VISION_MODEL","gpt-5-mini"))

    if st.button("▶ Run Thumbnail Analysis",type="primary",use_container_width=True):
        try:
            provider=None; analyzer=None
            if use_youtube:
                token=access_token_from_v2_files_read_only(Path(client_json),Path(token_json))
                provider=V2YouTubeReferenceProvider(token)
                analyzer=openai_thumbnail_text_analyzer(vision_key,model=vision_model) if vision_key else None
            # build_project_prompt_state is intentionally a single authoritative pipeline
            # call. Streamlit cannot observe its internal stages yet, so do not show a
            # misleading numeric progress percentage. Show the known current activity and
            # a live elapsed timer instead; the detailed stage result appears on completion.
            import time
            started=time.monotonic()
            status=st.status("Running thumbnail pipeline…",expanded=True)
            status.write("Reading project metadata and read-only V2 analytics")
            if use_youtube:
                status.write("YouTube search, filtering, thumbnail download and visual analysis will run in this pass")
            status.write("Cluster, text, composition and final-prompt gates will be evaluated before completion")
            with st.spinner("Analysis in progress — YouTube/vision can take a little time…"):
                state=build_project_prompt_state(
                    resolve_project(project_name),Path("Analytics/senior_health_analytics.db"),
                    cluster_db=Path("Thumbnail_Pipeline/db/thumbnail_intelligence.db"),
                    youtube_provider=provider,youtube_text_analyzer=analyzer)
            elapsed=time.monotonic()-started
            status.update(label=f"Analysis complete in {elapsed:.1f}s",state="complete",expanded=False)
            st.session_state["thumbnail_state"]=state
            st.session_state["thumbnail_project"]=project_name
        except Exception as exc:
            st.exception(exc)

    state=st.session_state.get("thumbnail_state")
    if state and st.session_state.get("thumbnail_project")==project_name:
        concept=state["concept"]; spec=state["composition"]; comp=spec.get("composition") or {}
        evidence=concept.get("evidence") or {}; cluster=state.get("discovered_cluster") or {}
        gate=evaluate_generation_gate(spec)
        a,b,c,d=st.columns(4)
        a.metric("Gate","APPROVED" if gate.get("approved") else "REVIEW")
        b.metric("Cluster",cluster.get("cluster_id") or "unclustered")
        c.metric("Similarity",f"{float(cluster.get('similarity') or 0):.3f}")
        d.metric("References",int((evidence.get("youtube_fallback") or {}).get("reference_count") or len(evidence.get("youtube_references") or [])))
        st.subheader("Immutable title"); st.info(state["immutable_title"])

        l,r=st.columns(2)
        with l:
            st.subheader("Composition")
            st.json({"layout":comp.get("layout"),"subject_placement":comp.get("subject_placement"),
                     "text_placement":comp.get("text_placement"),"safe_zone":comp.get("safe_zone"),
                     "unresolved_fields":gate.get("unresolved_fields") or []})
        with r:
            st.subheader("Thumbnail text candidates")
            candidates=comp.get("thumbnail_text_candidates") or []
            if candidates:
                selected=st.radio("Select final text",candidates,key="selected_thumb_text")
            else:
                selected=None; st.warning("No text candidate produced.")

        st.subheader("Current-topic visual evidence")
        subjects=comp.get("visual_subject_examples") or []
        if subjects:
            for x in subjects: st.write("• "+x)
        else: st.caption("No visual evidence available.")

        st.subheader("Final Prompt")
        if gate.get("approved"):
            result=export_final_thumbnail_prompt(spec,gate,selected_text=selected)
            st.code(result["final_prompt"],language=None)
            st.download_button("Download prompt",result["final_prompt"],file_name=f"{project_name}_thumbnail_prompt.txt",mime="text/plain")
        else:
            st.warning("Resolve the listed composition fields before final prompt export.")

with tab_refs:
    state=st.session_state.get("thumbnail_state")
    if not state:
        st.info("Run a project analysis first.")
    else:
        refs=((state["concept"].get("evidence") or {}).get("youtube_references") or [])
        st.subheader(f"YouTube References ({len(refs)})")
        if not refs: st.caption("No references loaded.")
        cols=st.columns(4)
        for i,ref in enumerate(refs):
            with cols[i%4]:
                local=ref.get("thumbnail_local_path") or ref.get("local_path") or ref.get("thumbnail_path")
                if local and Path(str(local)).is_file(): st.image(str(local),use_container_width=True)
                st.markdown(f"**{ref.get('video_title') or 'Reference'}**")
                if ref.get("external_thumbnail_visual_text"): st.caption("Text: "+str(ref["external_thumbnail_visual_text"]))
                st.caption("Layout: "+str(ref.get("external_thumbnail_structural_layout") or "unknown"))
                st.caption("Subject: "+str(ref.get("external_thumbnail_visible_subject") or "unknown"))

with tab_evidence:
    state=st.session_state.get("thumbnail_state")
    if not state:
        st.info("Run a project analysis first.")
    else:
        concept=state["concept"]; evidence=concept.get("evidence") or {}
        st.subheader("Dynamic Cluster"); st.json(state.get("discovered_cluster") or {})
        st.subheader("YouTube diagnostics"); st.json(evidence.get("youtube_fallback") or {})
        st.subheader("Text candidate ranking / rejection audit"); st.json(evidence.get("thumbnail_text_candidate_ranking") or [])
        st.subheader("Historical cluster prior"); st.json(evidence.get("cluster_prior_status") or {})
        st.subheader("Packaging association run"); st.json(evidence.get("packaging_association_run") or {})
        st.subheader("Composition provenance"); st.json(state["composition"].get("provenance") or {})

with tab_settings:
    s=get_dashboard_settings()
    with st.form("intelligence_settings"):
        minimum=st.number_input("Minimum Eligible Impressions",min_value=1,value=int(s["min_impressions"]),step=1)
        full=st.number_input("Full Reliability Impressions",min_value=1,value=int(s["full_reliability_impressions"]),step=1)
        submitted=st.form_submit_button("Save Settings")
        if submitted:
            try:
                save_dashboard_settings(min_impressions=int(minimum),full_reliability_impressions=int(full),actor="streamlit_dashboard")
                st.success("Settings saved.")
            except Exception as exc: st.error(str(exc))
    st.caption("Source of truth: Thumbnail_Pipeline/config/intelligence.json. Writes remain inside Thumbnail_Pipeline only.")

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st
from streamlit_sortables import sort_items

ROOT = Path(__file__).resolve().parents[1]
DYNAMIC_DIR = ROOT / "Templates" / "Dynamic"
STRATEGY_PATH = DYNAMIC_DIR / "outline_strategy.json"
BACKUP_DIR = DYNAMIC_DIR / "backups"


def _default_payload() -> dict:
    return {"version": 1, "blocks": []}


def _load_payload() -> dict:
    DYNAMIC_DIR.mkdir(parents=True, exist_ok=True)
    if not STRATEGY_PATH.is_file():
        return _default_payload()
    try:
        payload = json.loads(STRATEGY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        st.error("outline_strategy.json could not be read. The file was not changed.")
        st.stop()
    if not isinstance(payload, dict) or not isinstance(payload.get("blocks"), list):
        st.error("outline_strategy.json has an invalid structure. The file was not changed.")
        st.stop()
    return payload


def _save_payload(payload: dict) -> None:
    DYNAMIC_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if STRATEGY_PATH.is_file():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        shutil.copy2(STRATEGY_PATH, BACKUP_DIR / f"outline_strategy_{stamp}.json")
    STRATEGY_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _normalize_blocks(blocks: list) -> list[dict]:
    normalized = []
    for index, raw in enumerate(blocks, 1):
        if not isinstance(raw, dict):
            continue
        normalized.append({
            "id": str(raw.get("id") or uuid.uuid4().hex),
            "name": str(raw.get("name") or f"Block {index}"),
            "enabled": bool(raw.get("enabled", True)),
            "instruction": str(raw.get("instruction") or ""),
        })
    return normalized


st.set_page_config(page_title="Outline Builder", page_icon="🧩", layout="wide")
st.title("Outline Builder")
st.caption("Drag blocks into any order. Add, edit, enable, disable, or delete blocks. This page only saves Templates/Dynamic/outline_strategy.json and timestamped backups of its previous versions.")

payload = _load_payload()
if "outline_builder_blocks" not in st.session_state:
    st.session_state.outline_builder_blocks = _normalize_blocks(payload.get("blocks", []))

blocks = st.session_state.outline_builder_blocks

st.markdown("### Block order")
if blocks:
    label_to_id = {}
    sortable_labels = []
    for index, block in enumerate(blocks, 1):
        state = "ON" if block["enabled"] else "OFF"
        label = f"{index:02d} · {block['name']} · {state} · {block['id'][:8]}"
        sortable_labels.append(label)
        label_to_id[label] = block["id"]
    sorted_labels = sort_items(sortable_labels, direction="vertical", key="outline_block_sort")
    sorted_ids = [label_to_id[label] for label in sorted_labels]
    by_id = {block["id"]: block for block in blocks}
    blocks = [by_id[block_id] for block_id in sorted_ids]
    st.session_state.outline_builder_blocks = blocks
else:
    st.info("No blocks yet. Add your first block below.")

st.markdown("### Edit blocks")
for index, block in enumerate(list(blocks), 1):
    with st.expander(f"{index}. {block['name']} {'✓' if block['enabled'] else '— disabled'}"):
        block["name"] = st.text_input(
            "Block name",
            value=block["name"],
            key=f"outline_name_{block['id']}",
        )
        block["instruction"] = st.text_area(
            "Instruction",
            value=block["instruction"],
            height=130,
            key=f"outline_instruction_{block['id']}",
            help="Free-form instruction. The future Outline Agent integration can interpret this text dynamically.",
        )
        block["enabled"] = st.toggle(
            "Enabled",
            value=block["enabled"],
            key=f"outline_enabled_{block['id']}",
        )
        if st.button("Delete block", key=f"outline_delete_{block['id']}"):
            st.session_state.outline_builder_blocks = [
                item for item in blocks if item["id"] != block["id"]
            ]
            st.rerun()

st.markdown("### Add block")
with st.form("outline_add_block", clear_on_submit=True):
    new_name = st.text_input("New block name")
    new_instruction = st.text_area("New block instruction", height=120)
    new_enabled = st.checkbox("Enabled", value=True)
    add_clicked = st.form_submit_button("Add Block")
    if add_clicked:
        if not new_name.strip():
            st.error("Block name is required.")
        else:
            blocks.append({
                "id": uuid.uuid4().hex,
                "name": new_name.strip(),
                "enabled": bool(new_enabled),
                "instruction": new_instruction.strip(),
            })
            st.session_state.outline_builder_blocks = blocks
            st.rerun()

st.markdown("---")
left, right = st.columns([1, 3])
if left.button("Save JSON", type="primary", use_container_width=True):
    final_blocks = []
    for order, block in enumerate(st.session_state.outline_builder_blocks, 1):
        final_blocks.append({
            "id": block["id"],
            "order": order,
            "name": block["name"].strip() or f"Block {order}",
            "enabled": bool(block["enabled"]),
            "instruction": block["instruction"].strip(),
        })
    saved = {
        "version": 1,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "blocks": final_blocks,
    }
    try:
        _save_payload(saved)
    except OSError as exc:
        st.error(f"Could not save outline strategy: {exc}")
    else:
        st.session_state.outline_builder_blocks = _normalize_blocks(final_blocks)
        st.success("Saved Templates/Dynamic/outline_strategy.json. Previous JSON was backed up with date and time.")

right.code(str(STRATEGY_PATH.relative_to(ROOT)), language=None)

with st.expander("Current JSON preview"):
    preview = {
        "version": 1,
        "blocks": [
            {
                "id": block["id"],
                "order": index,
                "name": block["name"],
                "enabled": block["enabled"],
                "instruction": block["instruction"],
            }
            for index, block in enumerate(st.session_state.outline_builder_blocks, 1)
        ],
    }
    st.json(preview)

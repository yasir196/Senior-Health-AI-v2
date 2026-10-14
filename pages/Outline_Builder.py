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
    return {"version": 2, "blocks": []}


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


def _normalize_children(children: list) -> list[dict]:
    normalized = []
    for index, raw in enumerate(children or [], 1):
        if not isinstance(raw, dict):
            continue
        normalized.append({
            "id": str(raw.get("id") or uuid.uuid4().hex),
            "name": str(raw.get("name") or f"Child Block {index}"),
            "enabled": bool(raw.get("enabled", True)),
            "instruction": str(raw.get("instruction") or ""),
        })
    return normalized


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
            "children": _normalize_children(raw.get("children", [])),
        })
    return normalized


def _sortable(items: list[dict], key: str) -> list[dict]:
    if not items:
        return items
    label_to_id = {}
    labels = []
    for index, item in enumerate(items, 1):
        state = "ON" if item["enabled"] else "OFF"
        label = f"{index:02d} · {item['name']} · {state} · {item['id'][:8]}"
        labels.append(label)
        label_to_id[label] = item["id"]
    sorted_labels = sort_items(labels, direction="vertical", key=key)
    by_id = {item["id"]: item for item in items}
    return [by_id[label_to_id[label]] for label in sorted_labels]


def _serialized_blocks(blocks: list[dict]) -> list[dict]:
    result = []
    for parent_order, block in enumerate(blocks, 1):
        children = []
        for child_order, child in enumerate(block.get("children", []), 1):
            children.append({
                "id": child["id"],
                "order": child_order,
                "name": child["name"].strip() or f"Child Block {child_order}",
                "enabled": bool(child["enabled"]),
                "instruction": child["instruction"].strip(),
            })
        result.append({
            "id": block["id"],
            "order": parent_order,
            "name": block["name"].strip() or f"Block {parent_order}",
            "enabled": bool(block["enabled"]),
            "instruction": block["instruction"].strip(),
            "children": children,
        })
    return result


st.set_page_config(page_title="Outline Builder", page_icon="🧩", layout="wide")
st.title("Outline Builder")
st.caption(
    "Build a fully dynamic nested outline. Parent blocks and child blocks can be added, edited, enabled, disabled, deleted, and reordered. "
    "This page only saves Templates/Dynamic/outline_strategy.json and timestamped backups of its previous versions."
)

payload = _load_payload()
if "outline_builder_blocks" not in st.session_state:
    st.session_state.outline_builder_blocks = _normalize_blocks(payload.get("blocks", []))

blocks = st.session_state.outline_builder_blocks

st.markdown("### Parent block order")
if blocks:
    blocks = _sortable(blocks, "outline_parent_sort")
    st.session_state.outline_builder_blocks = blocks
else:
    st.info("No parent blocks yet. Add your first parent block below.")

st.markdown("### Parent blocks")
for parent_index, block in enumerate(list(blocks), 1):
    with st.expander(f"{parent_index}. {block['name']} {'✓' if block['enabled'] else '— disabled'}", expanded=False):
        block["name"] = st.text_input(
            "Parent block name",
            value=block["name"],
            key=f"outline_parent_name_{block['id']}",
        )
        block["instruction"] = st.text_area(
            "Parent instruction",
            value=block["instruction"],
            height=110,
            key=f"outline_parent_instruction_{block['id']}",
        )
        block["enabled"] = st.toggle(
            "Parent enabled",
            value=block["enabled"],
            key=f"outline_parent_enabled_{block['id']}",
        )

        st.markdown("#### Child block order")
        children = block.get("children", [])
        if children:
            children = _sortable(children, f"outline_child_sort_{block['id']}")
            block["children"] = children
        else:
            st.caption("No child blocks in this parent yet.")

        st.markdown("#### Edit child blocks")
        for child_index, child in enumerate(list(children), 1):
            with st.container(border=True):
                st.markdown(f"**{child_index}. {child['name']}**")
                child["name"] = st.text_input(
                    "Child block name",
                    value=child["name"],
                    key=f"outline_child_name_{child['id']}",
                )
                child["instruction"] = st.text_area(
                    "Child instruction",
                    value=child["instruction"],
                    height=90,
                    key=f"outline_child_instruction_{child['id']}",
                )
                child["enabled"] = st.toggle(
                    "Child enabled",
                    value=child["enabled"],
                    key=f"outline_child_enabled_{child['id']}",
                )
                if st.button("Delete child block", key=f"outline_child_delete_{child['id']}"):
                    block["children"] = [item for item in children if item["id"] != child["id"]]
                    st.rerun()

        st.markdown("#### Add child block")
        with st.form(f"outline_add_child_{block['id']}", clear_on_submit=True):
            child_name = st.text_input("New child block name")
            child_instruction = st.text_area("New child block instruction", height=90)
            child_enabled = st.checkbox("Enabled", value=True)
            add_child = st.form_submit_button("Add Child Block")
            if add_child:
                if not child_name.strip():
                    st.error("Child block name is required.")
                else:
                    block.setdefault("children", []).append({
                        "id": uuid.uuid4().hex,
                        "name": child_name.strip(),
                        "enabled": bool(child_enabled),
                        "instruction": child_instruction.strip(),
                    })
                    st.rerun()

        st.markdown("---")
        if st.button("Delete parent block", key=f"outline_parent_delete_{block['id']}"):
            st.session_state.outline_builder_blocks = [item for item in blocks if item["id"] != block["id"]]
            st.rerun()

st.markdown("### Add parent block")
with st.form("outline_add_parent_block", clear_on_submit=True):
    new_name = st.text_input("New parent block name")
    new_instruction = st.text_area("New parent block instruction", height=100)
    new_enabled = st.checkbox("Enabled", value=True)
    add_clicked = st.form_submit_button("Add Parent Block")
    if add_clicked:
        if not new_name.strip():
            st.error("Parent block name is required.")
        else:
            blocks.append({
                "id": uuid.uuid4().hex,
                "name": new_name.strip(),
                "enabled": bool(new_enabled),
                "instruction": new_instruction.strip(),
                "children": [],
            })
            st.session_state.outline_builder_blocks = blocks
            st.rerun()

st.markdown("---")
left, right = st.columns([1, 3])
if left.button("Save JSON", type="primary", use_container_width=True):
    final_blocks = _serialized_blocks(st.session_state.outline_builder_blocks)
    saved = {
        "version": 2,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "blocks": final_blocks,
    }
    try:
        _save_payload(saved)
    except OSError as exc:
        st.error(f"Could not save outline strategy: {exc}")
    else:
        st.session_state.outline_builder_blocks = _normalize_blocks(final_blocks)
        st.success("Saved nested outline_strategy.json. Previous JSON was backed up with date and time.")

right.code(str(STRATEGY_PATH.relative_to(ROOT)), language=None)

with st.expander("Current JSON preview"):
    st.json({
        "version": 2,
        "blocks": _serialized_blocks(st.session_state.outline_builder_blocks),
    })

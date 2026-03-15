#!/usr/bin/env python3
"""Build deterministic index pages from configurable definitions.

Configuration source:
- schema/automation.json -> indexes
"""

from __future__ import annotations

import csv
import json
import posixpath
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
INDEX_DIR = ROOT / "notes" / "indexes"
AUTOMATION_CONFIG = ROOT / "schema" / "automation.json"


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_config() -> Dict[str, Any]:
    if not AUTOMATION_CONFIG.exists():
        return {"indexes": []}
    with AUTOMATION_CONFIG.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {"indexes": []}
    return data


def load_entity_tables() -> List[str]:
    if not DATA_DIR.exists():
        return []

    entity_tables: List[str] = []
    for csv_path in sorted(DATA_DIR.glob("*.csv")):
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames or []
        if "id" in columns and "name" in columns:
            entity_tables.append(csv_path.stem)

    return entity_tables


def default_entity_index_definition(entity_table: str) -> Dict[str, Any]:
    title = f"All {entity_table.replace('_', ' ').title()}"
    return {
        "type": "entity_list",
        "entity_table": entity_table,
        "entity_id_column": "id",
        "title": title,
        "output": f"all_{entity_table}.md",
        "remove_when_empty": True,
    }


def build_entity_table_by_id() -> Dict[str, str]:
    table_by_id: Dict[str, str] = {}
    for table_name in load_entity_tables():
        csv_path = DATA_DIR / f"{table_name}.csv"
        if not csv_path.exists():
            continue
        for row in read_csv(csv_path):
            entity_id = (row.get("id") or "").strip()
            if entity_id:
                table_by_id[entity_id] = table_name
    return table_by_id


def build_note_link(from_dir: Path, table_name: str, entity_id: str) -> str:
    target = INDEX_DIR.parent / table_name / f"{entity_id}.md"
    rel = posixpath.relpath(target.as_posix(), start=from_dir.as_posix())
    return f"[{entity_id}]({rel})"


def render_entity_link(from_dir: Path, entity_id: str, table_by_id: Dict[str, str]) -> str:
    table_name = table_by_id.get(entity_id)
    if not table_name:
        return entity_id
    return build_note_link(from_dir, table_name, entity_id)


def build_index_plan(config: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], int, int]:
    configured_indexes = config.get("indexes", [])
    if not isinstance(configured_indexes, list):
        configured_indexes = []

    indexes: List[Dict[str, Any]] = []
    configured_outputs: set[str] = set()

    for item in configured_indexes:
        if not isinstance(item, dict):
            continue
        output = str(item.get("output", "")).strip()
        if output:
            configured_outputs.add(output)
        indexes.append(item)

    auto_added = 0
    auto_skipped = 0
    for entity_table in load_entity_tables():
        auto_item = default_entity_index_definition(entity_table)
        auto_output = str(auto_item["output"])
        if auto_output in configured_outputs:
            auto_skipped += 1
            continue
        indexes.append(auto_item)
        auto_added += 1

    return indexes, auto_added, auto_skipped


def write_if_changed(path: Path, content: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def remove_if_exists(path: Path) -> bool:
    if not path.exists():
        return False
    path.unlink()
    return True


def build_entity_list(
    title: str,
    entities: List[Dict[str, str]],
    entity_id_col: str,
    table_by_id: Dict[str, str],
) -> str:
    items = sorted((row.get(entity_id_col) or "").strip() for row in entities)
    items = [i for i in items if i]

    lines = [f"# {title}", ""]
    if not items:
        lines.append("- (none)")
    else:
        lines.extend([f"- {render_entity_link(INDEX_DIR, pid, table_by_id)}" for pid in items])
    lines.append("")
    return "\n".join(lines)


def build_grouped_relation(
    title: str,
    entities: List[Dict[str, str]],
    relations: List[Dict[str, str]],
    entity_id_col: str,
    relation_entity_fk: str,
    relation_item_fk: str,
    relation_role_col: str,
    role: str,
    table_by_id: Dict[str, str],
) -> str:
    by_entity: Dict[str, List[str]] = {}

    for row in relations:
        item_id = (row.get(relation_item_fk) or "").strip()
        entity_id = (row.get(relation_entity_fk) or "").strip()
        row_role = (row.get(relation_role_col) or "").strip().lower()
        if not item_id or not entity_id or row_role != role.lower():
            continue
        by_entity.setdefault(entity_id, []).append(item_id)

    lines = [f"# {title}", ""]

    entity_ids = sorted((r.get(entity_id_col) or "").strip() for r in entities)
    entity_ids = [eid for eid in entity_ids if eid]

    if not entity_ids:
        lines.append("- (none)")
        lines.append("")
        return "\n".join(lines)

    for entity_id in entity_ids:
        lines.append(f"## {render_entity_link(INDEX_DIR, entity_id, table_by_id)}")
        items = sorted(set(by_entity.get(entity_id, [])))
        if items:
            lines.extend([f"- {render_entity_link(INDEX_DIR, item_id, table_by_id)}" for item_id in items])
        else:
            lines.append("- (none)")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    config = load_config()
    indexes, auto_added, auto_skipped = build_index_plan(config)
    if not indexes:
        print("Skipped index generation: no index definitions found and no entity tables discovered")
        return 0

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    table_by_id = build_entity_table_by_id()

    changed = 0

    for item in indexes:
        if not isinstance(item, dict):
            continue

        output = str(item.get("output", "")).strip()
        index_type = str(item.get("type", "")).strip().lower()
        title = str(item.get("title", "")).strip() or "Index"
        if not output or not index_type:
            continue

        output_path = INDEX_DIR / output
        remove_when_empty = bool(item.get("remove_when_empty", True))

        if index_type == "entity_list":
            entity_table = str(item.get("entity_table", "")).strip()
            entity_id_col = str(item.get("entity_id_column", "id")).strip() or "id"
            entity_csv = DATA_DIR / f"{entity_table}.csv"
            if not entity_table or not entity_csv.exists():
                changed += int(remove_if_exists(output_path))
                continue

            entities = read_csv(entity_csv)
            entity_ids = [
                (row.get(entity_id_col) or "").strip()
                for row in entities
                if (row.get(entity_id_col) or "").strip()
            ]
            if not entity_ids and remove_when_empty:
                changed += int(remove_if_exists(output_path))
                continue

            content = build_entity_list(title, entities, entity_id_col, table_by_id)
            changed += int(write_if_changed(output_path, content))
            continue

        if index_type == "grouped_relation":
            entity_table = str(item.get("entity_table", "")).strip()
            relation_table = str(item.get("relation_table", "")).strip()
            entity_id_col = str(item.get("entity_id_column", "id")).strip() or "id"
            relation_entity_fk = str(item.get("relation_entity_fk", "")).strip()
            relation_item_fk = str(item.get("relation_item_fk", "")).strip()
            relation_role_col = str(item.get("relation_role_column", "role")).strip() or "role"
            role = str(item.get("role", "")).strip()

            entity_csv = DATA_DIR / f"{entity_table}.csv"
            relation_csv = DATA_DIR / f"{relation_table}.csv"
            if (
                not entity_table
                or not relation_table
                or not relation_entity_fk
                or not relation_item_fk
                or not role
                or not entity_csv.exists()
                or not relation_csv.exists()
            ):
                changed += int(remove_if_exists(output_path))
                continue

            entities = read_csv(entity_csv)
            relations = read_csv(relation_csv)
            entity_ids = [
                (row.get(entity_id_col) or "").strip()
                for row in entities
                if (row.get(entity_id_col) or "").strip()
            ]
            if not entity_ids and remove_when_empty:
                changed += int(remove_if_exists(output_path))
                continue

            content = build_grouped_relation(
                title=title,
                entities=entities,
                relations=relations,
                entity_id_col=entity_id_col,
                relation_entity_fk=relation_entity_fk,
                relation_item_fk=relation_item_fk,
                relation_role_col=relation_role_col,
                role=role,
                table_by_id=table_by_id,
            )
            changed += int(write_if_changed(output_path, content))
            continue

        # Unknown index type: remove stale output to avoid carrying stale docs.
        changed += int(remove_if_exists(output_path))

    print(
        "Built index pages: "
        f"changed={changed}, "
        f"auto_added={auto_added}, "
        f"auto_skipped_due_to_config={auto_skipped}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

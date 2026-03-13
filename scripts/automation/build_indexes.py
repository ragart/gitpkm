#!/usr/bin/env python3
"""Build deterministic index pages from configurable definitions.

Configuration source:
- schema/automation.json -> indexes
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

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


def build_entity_list(title: str, entities: List[Dict[str, str]], entity_id_col: str) -> str:
    items = sorted((row.get(entity_id_col) or "").strip() for row in entities)
    items = [i for i in items if i]

    lines = [f"# {title}", ""]
    if not items:
        lines.append("- (none)")
    else:
        lines.extend([f"- [[{pid}]]" for pid in items])
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
        lines.append(f"## [[{entity_id}]]")
        items = sorted(set(by_entity.get(entity_id, [])))
        if items:
            lines.extend([f"- [[{item_id}]]" for item_id in items])
        else:
            lines.append("- (none)")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    config = load_config()
    indexes = config.get("indexes", [])
    if not isinstance(indexes, list) or not indexes:
        print("Skipped index generation: no indexes configured in schema/automation.json")
        return 0

    INDEX_DIR.mkdir(parents=True, exist_ok=True)

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

            content = build_entity_list(title, entities, entity_id_col)
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
            )
            changed += int(write_if_changed(output_path, content))
            continue

        # Unknown index type: remove stale output to avoid carrying stale docs.
        changed += int(remove_if_exists(output_path))

    print(f"Built index pages: changed={changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

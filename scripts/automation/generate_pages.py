#!/usr/bin/env python3
"""Create baseline entity notes and render in-note generated blocks.

Supported generated block directives:
- header
- list:<table_name>
- table:<table_name>
"""

from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
NOTES_DIR = ROOT / "notes"

MARKER_END = "<!-- GENERATED END -->"
START_RE = re.compile(
    r"^<!-- GENERATED START: (?P<directive>[a-z][a-z0-9_]*(?::[a-z][a-z0-9_]*)?) -->$",
    re.MULTILINE,
)
BLOCK_RE = re.compile(
    r"(?ms)^<!-- GENERATED START: (?P<directive>[a-z][a-z0-9_]*(?::[a-z][a-z0-9_]*)?) -->\n.*?\n<!-- GENERATED END -->$"
)
HEADER_PREFIX_RE = re.compile(
    r"(?ms)^---\n.*?\n---\n(?:\n)*<!-- GENERATED START: header -->\n.*?\n<!-- GENERATED END -->\n*"
)


@dataclass
class TableData:
    name: str
    columns: List[str]
    rows: List[Dict[str, str]]

    @property
    def is_entity_table(self) -> bool:
        return "id" in self.columns and "name" in self.columns


def read_csv(path: Path) -> TableData:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return TableData(path.stem, reader.fieldnames or [], list(reader))


def load_tables() -> Dict[str, TableData]:
    if not DATA_DIR.exists():
        return {}
    tables: Dict[str, TableData] = {}
    for path in sorted(DATA_DIR.glob("*.csv")):
        tables[path.stem] = read_csv(path)
    return tables


def build_entity_lookup(tables: Dict[str, TableData]) -> Tuple[Dict[str, Dict[str, str]], Dict[str, str]]:
    rows_by_id: Dict[str, Dict[str, str]] = {}
    table_by_id: Dict[str, str] = {}

    for table in tables.values():
        if not table.is_entity_table:
            continue
        for row in table.rows:
            entity_id = (row.get("id") or "").strip()
            if not entity_id:
                continue
            rows_by_id[entity_id] = row
            table_by_id[entity_id] = table.name

    return rows_by_id, table_by_id


def render_header_prefix(entity_id: str, entity_name: str, entity_type: str) -> str:
    return "\n".join(
        [
            "---",
            f"id: {entity_id}",
            f"type: {entity_type}",
            "---",
            "<!-- GENERATED START: header -->",
            f"# {entity_name}",
            MARKER_END,
            "",
            "",
        ]
    )


def create_entity_note(entity_id: str, entity_name: str, entity_type: str) -> str:
    return render_header_prefix(entity_id, entity_name, entity_type) + "Entity note.\n"


def escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def render_link_cell(column: str, value: str, all_ids: set[str]) -> str:
    clean = value.strip()
    if not clean:
        return ""
    if column == "id" or (column.endswith("_id") and clean in all_ids):
        return f"[[{clean}]]"
    return clean


def render_list_block(table_name: str, tables: Dict[str, TableData]) -> str:
    table = tables.get(table_name)
    lines = [f"<!-- GENERATED START: list:{table_name} -->"]

    if not table or "id" not in table.columns:
        lines.append("- (none)")
        lines.append(MARKER_END)
        return "\n".join(lines)

    items = sorted((row.get("id") or "").strip() for row in table.rows)
    items = [item for item in items if item]
    if items:
        lines.extend(f"- [[{item}]]" for item in items)
    else:
        lines.append("- (none)")

    lines.append(MARKER_END)
    return "\n".join(lines)


def render_table_block(table_name: str, tables: Dict[str, TableData], all_ids: set[str]) -> str:
    table = tables.get(table_name)
    lines = [f"<!-- GENERATED START: table:{table_name} -->"]

    if not table or not table.columns:
        lines.append("- (none)")
        lines.append(MARKER_END)
        return "\n".join(lines)

    rows = sorted(table.rows, key=lambda row: (row.get("id") or "").strip())
    lines.append("| " + " | ".join(table.columns) + " |")
    lines.append("| " + " | ".join("---" for _ in table.columns) + " |")

    for row in rows:
        rendered = []
        for column in table.columns:
            value = render_link_cell(column, row.get(column, ""), all_ids)
            rendered.append(escape_cell(value))
        lines.append("| " + " | ".join(rendered) + " |")

    if not rows:
        lines.append("| " + " | ".join("(none)" for _ in table.columns) + " |")

    lines.append(MARKER_END)
    return "\n".join(lines)


def render_directive_block(directive: str, tables: Dict[str, TableData], all_ids: set[str]) -> str | None:
    if directive == "header":
        return None

    kind, _, target = directive.partition(":")
    if kind == "list" and target:
        return render_list_block(target, tables)
    if kind == "table" and target:
        return render_table_block(target, tables, all_ids)
    return None


def replace_header_prefix(
    content: str,
    entity_id: str,
    entity_name: str,
    entity_type: str,
) -> str:
    rendered = render_header_prefix(entity_id, entity_name, entity_type)
    if HEADER_PREFIX_RE.match(content):
        return HEADER_PREFIX_RE.sub(rendered, content, count=1)
    return content


def render_note(
    content: str,
    tables: Dict[str, TableData],
    all_ids: set[str],
) -> Tuple[str, bool]:
    changed = False

    def repl(match: re.Match[str]) -> str:
        nonlocal changed
        directive = match.group("directive")
        block = render_directive_block(directive, tables, all_ids)
        if block is None:
            return match.group(0)
        if block != match.group(0):
            changed = True
        return block

    rendered = BLOCK_RE.sub(repl, content)
    return rendered, changed


def ensure_entity_notes(
    tables: Dict[str, TableData],
    rows_by_id: Dict[str, Dict[str, str]],
    table_by_id: Dict[str, str],
) -> int:
    created = 0

    for entity_id in sorted(rows_by_id):
        row = rows_by_id[entity_id]
        table_name = table_by_id[entity_id]
        notes_dir = NOTES_DIR / table_name
        notes_dir.mkdir(parents=True, exist_ok=True)
        note_path = notes_dir / f"{entity_id}.md"
        if note_path.exists():
            continue

        entity_name = (row.get("name") or "").strip() or entity_id
        entity_type = table_name
        note_path.write_text(create_entity_note(entity_id, entity_name, entity_type), encoding="utf-8")
        created += 1

    return created


def render_notes(tables: Dict[str, TableData], rows_by_id: Dict[str, Dict[str, str]], table_by_id: Dict[str, str]) -> int:
    if not NOTES_DIR.exists():
        return 0

    all_ids = set(rows_by_id)
    updated = 0

    for note_path in sorted(NOTES_DIR.rglob("*.md")):
        content = note_path.read_text(encoding="utf-8")
        new_content = content
        entity_id = note_path.stem
        if entity_id in rows_by_id and START_RE.search(content):
            row = rows_by_id[entity_id]
            table_name = table_by_id[entity_id]
            entity_name = (row.get("name") or "").strip() or entity_id
            entity_type = table_name
            new_content = replace_header_prefix(new_content, entity_id, entity_name, entity_type)

        new_content, _ = render_note(new_content, tables, all_ids)
        if new_content != content:
            note_path.write_text(new_content, encoding="utf-8")
            updated += 1

    return updated


def generate() -> int:
    tables = load_tables()
    if not tables:
        print("Skipped note generation: no csv files found in data/")
        return 0

    rows_by_id, table_by_id = build_entity_lookup(tables)
    created = ensure_entity_notes(tables, rows_by_id, table_by_id)
    updated = render_notes(tables, rows_by_id, table_by_id)

    print(f"Generated notes: created={created}, updated={updated}")
    return 0


def main() -> int:
    return generate()


if __name__ == "__main__":
    sys.exit(main())

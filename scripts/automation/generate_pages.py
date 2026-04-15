#!/usr/bin/env python3
"""Create baseline entity notes and render in-note generated blocks.

Supported generated block directives:
- header
- list:<table_name>
- table:<table_name>
"""

from __future__ import annotations

import csv
import posixpath
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


def yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render_header_prefix(entity_id: str, entity_type: str, row: Dict[str, str], columns: List[str]) -> str:
    entity_name = (row.get("name") or "").strip() or entity_id
    frontmatter_lines = [
        "---",
        f"id: {entity_id}",
        f"type: {entity_type}",
    ]

    for column in columns:
        if column in {"id", "type"}:
            continue
        value = (row.get(column) or "").strip()
        frontmatter_lines.append(f"{column}: {yaml_quote(value)}")

    frontmatter_lines.extend(
        [
            "---",
            "<!-- GENERATED START: header -->",
            f"# {entity_name}",
            MARKER_END,
            "",
            "",
        ]
    )
    return "\n".join(frontmatter_lines)


def create_entity_note(entity_id: str, entity_type: str, row: Dict[str, str], columns: List[str]) -> str:
    return render_header_prefix(entity_id, entity_type, row, columns) + "Entity note.\n"


def escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def build_note_link(note_path: Path, table_name: str, entity_id: str) -> str:
    target = NOTES_DIR / table_name / f"{entity_id}.md"
    rel = Path(posixpath.relpath(target.as_posix(), start=note_path.parent.as_posix()))
    return f"[{entity_id}]({rel.as_posix()})"


def render_link_cell(
    note_path: Path,
    row_table_name: str,
    column: str,
    value: str,
    table_by_id: Dict[str, str],
    entity_tables: set[str],
) -> str:
    clean = value.strip()
    if not clean:
        return ""

    if column == "id" and row_table_name in entity_tables:
        return build_note_link(note_path, row_table_name, clean)

    if column.endswith("_id") and clean in table_by_id:
        return build_note_link(note_path, table_by_id[clean], clean)

    return clean


def render_list_block(note_path: Path, table_name: str, tables: Dict[str, TableData]) -> str:
    table = tables.get(table_name)
    lines = [f"<!-- GENERATED START: list:{table_name} -->"]

    if not table or "id" not in table.columns:
        lines.append("- (none)")
        lines.append(MARKER_END)
        return "\n".join(lines)

    items = sorted((row.get("id") or "").strip() for row in table.rows)
    items = [item for item in items if item]
    if items:
        lines.extend(f"- {build_note_link(note_path, table_name, item)}" for item in items)
    else:
        lines.append("- (none)")

    lines.append(MARKER_END)
    return "\n".join(lines)


def render_table_block(
    note_path: Path,
    table_name: str,
    tables: Dict[str, TableData],
    table_by_id: Dict[str, str],
    entity_tables: set[str],
) -> str:
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
            value = render_link_cell(
                note_path=note_path,
                row_table_name=table_name,
                column=column,
                value=row.get(column, ""),
                table_by_id=table_by_id,
                entity_tables=entity_tables,
            )
            rendered.append(escape_cell(value))
        lines.append("| " + " | ".join(rendered) + " |")

    if not rows:
        lines.append("| " + " | ".join("(none)" for _ in table.columns) + " |")

    lines.append(MARKER_END)
    return "\n".join(lines)


def render_directive_block(
    note_path: Path,
    directive: str,
    tables: Dict[str, TableData],
    table_by_id: Dict[str, str],
    entity_tables: set[str],
) -> str | None:
    if directive == "header":
        return None

    kind, _, target = directive.partition(":")
    if kind == "list" and target:
        return render_list_block(note_path, target, tables)
    if kind == "table" and target:
        return render_table_block(note_path, target, tables, table_by_id, entity_tables)
    return None


def replace_header_prefix(
    content: str,
    entity_id: str,
    entity_type: str,
    row: Dict[str, str],
    columns: List[str],
) -> str:
    rendered = render_header_prefix(entity_id, entity_type, row, columns)
    if HEADER_PREFIX_RE.match(content):
        return HEADER_PREFIX_RE.sub(rendered, content, count=1)
    return content


def render_note(
    note_path: Path,
    content: str,
    tables: Dict[str, TableData],
    table_by_id: Dict[str, str],
    entity_tables: set[str],
) -> Tuple[str, bool]:
    changed = False

    def repl(match: re.Match[str]) -> str:
        nonlocal changed
        directive = match.group("directive")
        block = render_directive_block(note_path, directive, tables, table_by_id, entity_tables)
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

        entity_type = table_name
        table = tables[table_name]
        note_path.write_text(create_entity_note(entity_id, entity_type, row, table.columns), encoding="utf-8")
        created += 1

    return created


def render_notes(tables: Dict[str, TableData], rows_by_id: Dict[str, Dict[str, str]], table_by_id: Dict[str, str]) -> int:
    if not NOTES_DIR.exists():
        return 0

    updated = 0
    entity_tables = {table.name for table in tables.values() if table.is_entity_table}

    for note_path in sorted(NOTES_DIR.rglob("*.md")):
        content = note_path.read_text(encoding="utf-8")
        new_content = content
        entity_id = note_path.stem
        if entity_id in rows_by_id and START_RE.search(content):
            row = rows_by_id[entity_id]
            table_name = table_by_id[entity_id]
            entity_type = table_name
            new_content = replace_header_prefix(new_content, entity_id, entity_type, row, tables[table_name].columns)

        new_content, _ = render_note(note_path, new_content, tables, table_by_id, entity_tables)
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

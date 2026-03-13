#!/usr/bin/env python3
"""Validate a GitPKM repository against the documented schema contract.

Checks implemented:
- ID format and duplicates
- Required columns by table type
- Foreign-key resolution
- Optional display name consistency (<prefix>_id + <prefix>_name)
- Markdown wiki-link resolution
- Frontmatter id consistency
- Missing/orphan note warnings
"""

from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
NOTES_DIR = ROOT / "notes"

ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
WIKI_LINK_RE = re.compile(r"\[\[([a-zA-Z0-9_\-]+)\]\]")
MARKER_START = "<!-- GENERATED START -->"
MARKER_END = "<!-- GENERATED END -->"
MARKER_START_RE = re.compile(
    r"^<!-- GENERATED START(?:: (?P<directive>[a-z][a-z0-9_]*(?::[a-z][a-z0-9_]*)?))? -->$"
)


@dataclass
class TableData:
    name: str
    path: Path
    columns: List[str]
    rows: List[Dict[str, str]]

    @property
    def is_entity_table(self) -> bool:
        return "name" in self.columns

    @property
    def fk_columns(self) -> List[str]:
        return [c for c in self.columns if c.endswith("_id") and c != "id"]


@dataclass
class Findings:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def load_csv_tables(findings: Findings) -> Dict[str, TableData]:
    tables: Dict[str, TableData] = {}

    if not DATA_DIR.exists():
        findings.warn(f"missing data directory: {DATA_DIR.relative_to(ROOT)}")
        return tables

    csv_files = sorted(DATA_DIR.glob("*.csv"))
    if not csv_files:
        findings.warn(f"no csv files found in: {DATA_DIR.relative_to(ROOT)}")
        return tables

    for csv_path in csv_files:
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames or []
            rows = list(reader)

        table_name = csv_path.stem
        tables[table_name] = TableData(
            name=table_name,
            path=csv_path,
            columns=columns,
            rows=rows,
        )

    return tables


def validate_required_columns(tables: Dict[str, TableData], findings: Findings) -> None:
    for table in tables.values():
        if "id" not in table.columns:
            findings.error(f"{table.path.relative_to(ROOT)} missing required column: id")
            continue

        if table.is_entity_table:
            missing = [c for c in ["id", "name"] if c not in table.columns]
            if missing:
                findings.error(
                    f"{table.path.relative_to(ROOT)} missing required columns for entity table: {', '.join(missing)}"
                )
        else:
            if not table.fk_columns:
                findings.error(
                    f"{table.path.relative_to(ROOT)} relationship table must include at least one *_id column"
                )


def validate_ids_and_duplicates(
    tables: Dict[str, TableData], findings: Findings
) -> Tuple[Set[str], Dict[str, str]]:
    all_ids: Set[str] = set()
    id_to_table: Dict[str, str] = {}

    for table in tables.values():
        if "id" not in table.columns:
            continue

        seen: Set[str] = set()
        for i, row in enumerate(table.rows, start=2):
            rid = (row.get("id") or "").strip()
            loc = f"{table.path.relative_to(ROOT)}:{i}"

            if not rid:
                findings.error(f"{loc} empty id")
                continue

            if not ID_RE.match(rid):
                findings.error(f"{loc} invalid id format: {rid}")

            if rid in seen:
                findings.error(f"{loc} duplicate id in table: {rid}")
            seen.add(rid)

            if rid in all_ids:
                findings.error(f"{loc} duplicate id across tables: {rid}")
            all_ids.add(rid)
            id_to_table[rid] = table.name

    return all_ids, id_to_table


def infer_reference_table(fk_column: str, tables: Dict[str, TableData]) -> str | None:
    base = fk_column[: -len("_id")]
    if base in tables:
        return base
    return None


def validate_foreign_keys(
    tables: Dict[str, TableData], all_ids: Set[str], findings: Findings
) -> None:
    for table in tables.values():
        for fk in table.fk_columns:
            ref_table = infer_reference_table(fk, tables)
            if ref_table is None:
                findings.warn(
                    f"{table.path.relative_to(ROOT)} cannot infer reference table for column: {fk}"
                )

            for i, row in enumerate(table.rows, start=2):
                value = (row.get(fk) or "").strip()
                if not value:
                    continue

                loc = f"{table.path.relative_to(ROOT)}:{i}"
                if not ID_RE.match(value):
                    findings.error(f"{loc} invalid foreign key format in {fk}: {value}")
                    continue

                if value not in all_ids:
                    findings.error(f"{loc} unresolved foreign key {fk}: {value}")


def build_name_lookup(tables: Dict[str, TableData]) -> Dict[str, Dict[str, str]]:
    lookup: Dict[str, Dict[str, str]] = {}

    for table in tables.values():
        if "id" not in table.columns or "name" not in table.columns:
            continue
        lookup[table.name] = {
            (r.get("id") or "").strip(): (r.get("name") or "").strip()
            for r in table.rows
            if (r.get("id") or "").strip()
        }

    return lookup


def validate_display_columns(tables: Dict[str, TableData], findings: Findings) -> None:
    name_lookup = build_name_lookup(tables)

    for table in tables.values():
        cols = set(table.columns)
        id_cols = [c for c in table.columns if c.endswith("_id") and c != "id"]
        for id_col in id_cols:
            prefix = id_col[: -len("_id")]
            name_col = f"{prefix}_name"
            if name_col not in cols:
                continue

            ref_table = infer_reference_table(id_col, tables)
            if ref_table is None or ref_table not in name_lookup:
                findings.warn(
                    f"{table.path.relative_to(ROOT)} cannot validate display column pair: {id_col}/{name_col}"
                )
                continue

            for i, row in enumerate(table.rows, start=2):
                ref_id = (row.get(id_col) or "").strip()
                shown_name = (row.get(name_col) or "").strip()
                if not ref_id or not shown_name:
                    continue

                expected_name = name_lookup[ref_table].get(ref_id)
                if expected_name and expected_name != shown_name:
                    findings.warn(
                        f"{table.path.relative_to(ROOT)}:{i} display mismatch {name_col}={shown_name!r}, expected {expected_name!r}"
                    )


def parse_frontmatter_id(markdown: str) -> str | None:
    frontmatter = parse_frontmatter(markdown)
    return frontmatter.get("id")


def parse_frontmatter(markdown: str) -> Dict[str, str]:
    if not markdown.startswith("---\n"):
        return {}

    end = markdown.find("\n---\n", 4)
    if end == -1:
        return {}

    block = markdown[4:end]
    result: Dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def infer_allowed_entity_types(tables: Dict[str, TableData]) -> Set[str]:
    allowed: Set[str] = set()
    for table_name, table in tables.items():
        if not table.is_entity_table:
            continue
        allowed.add(table_name)
    return allowed


def validate_generated_markers(note: Path, text: str, findings: Findings) -> None:
    lines = text.splitlines()
    in_block = False
    start_line = 0

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if MARKER_START_RE.match(stripped):
            if in_block:
                findings.error(
                    f"{note.relative_to(ROOT)}:{idx} nested GENERATED START marker"
                )
            in_block = True
            start_line = idx
            continue

        if stripped == MARKER_END:
            if not in_block:
                findings.error(
                    f"{note.relative_to(ROOT)}:{idx} GENERATED END marker without matching start"
                )
                continue
            in_block = False

    if in_block:
        findings.error(
            f"{note.relative_to(ROOT)}:{start_line} GENERATED START marker without matching end"
        )


def collect_note_files() -> List[Path]:
    if not NOTES_DIR.exists():
        return []
    return sorted(p for p in NOTES_DIR.rglob("*.md") if p.is_file())


def validate_notes(
    tables: Dict[str, TableData], all_ids: Set[str], findings: Findings
) -> None:
    note_files = collect_note_files()
    notes_by_stem: Dict[str, Path] = {p.stem: p for p in note_files}
    allowed_entity_types = infer_allowed_entity_types(tables)

    def is_index_note(path: Path) -> bool:
        try:
            return path.relative_to(NOTES_DIR).parts[:1] == ("indexes",)
        except ValueError:
            return False

    for note in note_files:
        text = note.read_text(encoding="utf-8")
        validate_generated_markers(note, text, findings)

        frontmatter = parse_frontmatter(text)
        fm_id = frontmatter.get("id")
        if fm_id and not ID_RE.match(fm_id):
            findings.error(
                f"{note.relative_to(ROOT)} invalid frontmatter id format: {fm_id}"
            )

        if fm_id and fm_id != note.stem:
            findings.error(
                f"{note.relative_to(ROOT)} frontmatter id {fm_id!r} does not match filename stem {note.stem!r}"
            )

        fm_type = frontmatter.get("type")
        if (
            fm_type
            and allowed_entity_types
            and not is_index_note(note)
            and fm_type not in allowed_entity_types
        ):
            findings.error(
                f"{note.relative_to(ROOT)} invalid frontmatter type {fm_type!r}; allowed: {', '.join(sorted(allowed_entity_types))}"
            )

        for link in WIKI_LINK_RE.findall(text):
            if link not in all_ids:
                findings.error(f"{note.relative_to(ROOT)} unresolved wiki link: [[{link}]]")

        if text.startswith("<!-- GENERATED START: header -->"):
            findings.error(
                f"{note.relative_to(ROOT)} header block must come after frontmatter, not before it"
            )

    # Note coverage checks only for entity rows.
    entity_ids: Set[str] = set()
    for table in tables.values():
        if not table.is_entity_table or "id" not in table.columns:
            continue
        for row in table.rows:
            rid = (row.get("id") or "").strip()
            if rid:
                entity_ids.add(rid)

    for rid in sorted(entity_ids):
        if rid not in notes_by_stem:
            findings.warn(f"missing note for entity id: {rid}")
            continue

        note = notes_by_stem[rid]
        text = note.read_text(encoding="utf-8")
        fm_id = parse_frontmatter_id(text)
        if fm_id and fm_id != rid:
            findings.error(
                f"{note.relative_to(ROOT)} frontmatter id {fm_id!r} does not match csv entity id {rid!r}"
            )

    for note in note_files:
        stem = note.stem
        if is_index_note(note):
            continue
        if stem not in entity_ids:
            findings.warn(f"orphan note (no matching entity row): {note.relative_to(ROOT)}")


def print_report(findings: Findings) -> None:
    if findings.errors:
        print("Errors:")
        for e in findings.errors:
            print(f"- {e}")

    if findings.warnings:
        print("Warnings:")
        for w in findings.warnings:
            print(f"- {w}")

    print(
        f"Summary: {len(findings.errors)} error(s), {len(findings.warnings)} warning(s)"
    )


def main() -> int:
    findings = Findings()

    tables = load_csv_tables(findings)
    if not tables:
        validate_notes(tables, set(), findings)
        print_report(findings)
        return 1 if findings.errors else 0

    validate_required_columns(tables, findings)
    all_ids, _ = validate_ids_and_duplicates(tables, findings)
    validate_foreign_keys(tables, all_ids, findings)
    validate_display_columns(tables, findings)
    validate_notes(tables, all_ids, findings)

    print_report(findings)
    return 1 if findings.errors else 0


if __name__ == "__main__":
    sys.exit(main())

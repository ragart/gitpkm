#!/usr/bin/env python3
"""Minimal CLI for managing PKM CSV entities and relations."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from scripts.automation import build_indexes, generate_pages

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    slug = re.sub(r"_+", "_", slug)
    return slug or "item"


def parse_key_value(items: List[str]) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"invalid key=value pair: {item}")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"invalid key=value pair: {item}")
        parsed[key] = value.strip()
    return parsed


def read_table(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def write_table(path: Path, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_tables() -> Dict[str, Tuple[List[str], List[Dict[str, str]]]]:
    tables: Dict[str, Tuple[List[str], List[Dict[str, str]]]] = {}
    if not DATA_DIR.exists():
        return tables
    for path in sorted(DATA_DIR.glob("*.csv")):
        tables[path.stem] = read_table(path)
    return tables


def build_id_lookup(tables: Dict[str, Tuple[List[str], List[Dict[str, str]]]]) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for table_name, (fieldnames, rows) in tables.items():
        if "id" not in fieldnames:
            continue
        for row in rows:
            entity_id = (row.get("id") or "").strip()
            if entity_id:
                lookup[entity_id] = table_name
    return lookup


def ensure_entity_table(table_name: str) -> Tuple[Path, List[str], List[Dict[str, str]]]:
    path = DATA_DIR / f"{table_name}.csv"
    if not path.exists():
        return path, ["id", "name"], []

    fieldnames, rows = read_table(path)
    required = {"id", "name"}
    if not required.issubset(fieldnames):
        missing = ", ".join(sorted(required - set(fieldnames)))
        raise ValueError(f"{path.relative_to(ROOT)} missing required columns: {missing}")
    return path, fieldnames, rows


def infer_relation_table(
    source_table: str,
    target_table: str,
    tables: Dict[str, Tuple[List[str], List[Dict[str, str]]]],
) -> Tuple[str, str, str]:
    source_fk = f"{source_table}_id"
    target_fk = f"{target_table}_id"
    candidates: List[str] = []

    for table_name, (fieldnames, _) in tables.items():
        if source_fk in fieldnames and target_fk in fieldnames:
            candidates.append(table_name)

    if len(candidates) != 1:
        if not candidates:
            raise ValueError(
                f"could not infer a relationship table for {source_table} and {target_table}; use --table"
            )
        raise ValueError(
            f"multiple relationship tables match {source_table} and {target_table}: {', '.join(sorted(candidates))}; use --table"
        )

    return candidates[0], source_fk, target_fk


def run_automation() -> None:
    generate_pages.generate()
    build_indexes.main()


def command_new(args: argparse.Namespace) -> int:
    entity_type = args.entity_type.strip().lower()
    table_name = entity_type
    table_path, fieldnames, rows = ensure_entity_table(table_name)
    extra_values = parse_key_value(args.set_values)

    reserved = {"id", "name"}
    invalid_reserved = sorted(reserved.intersection(extra_values.keys()))
    if invalid_reserved:
        if "id" in invalid_reserved:
            raise ValueError("do not set id with --set; use --id")
        raise ValueError("do not set name with --set; use the <name> positional argument")

    unknown_columns = sorted(set(extra_values.keys()) - set(fieldnames))
    if unknown_columns:
        allowed_columns = ", ".join(sorted(fieldnames))
        raise ValueError(
            f"unknown columns for {table_name}: {', '.join(unknown_columns)}; allowed columns: {allowed_columns}"
        )

    entity_id = args.id or f"{entity_type}_{slugify(args.name)}"
    existing_ids = {(row.get("id") or "").strip() for row in rows}
    if entity_id in existing_ids:
        print(f"Entity already exists: {entity_id}")
        return 0

    row = {field: "" for field in fieldnames}
    row["id"] = entity_id
    row["name"] = args.name.strip()
    for key, value in extra_values.items():
        row[key] = value
    rows.append(row)
    write_table(table_path, fieldnames, rows)

    run_automation()
    print(f"Created {entity_type}: {entity_id}")
    return 0


def command_link(args: argparse.Namespace) -> int:
    tables = load_tables()
    id_lookup = build_id_lookup(tables)

    source_id = args.source_id.strip()
    target_id = args.target_id.strip()
    if source_id not in id_lookup:
        raise ValueError(f"unknown source id: {source_id}")
    if target_id not in id_lookup:
        raise ValueError(f"unknown target id: {target_id}")

    source_table = id_lookup[source_id]
    target_table = id_lookup[target_id]
    source_fk = f"{source_table}_id"
    target_fk = f"{target_table}_id"

    if args.table:
        relation_table = args.table.strip()
    else:
        relation_table, source_fk, target_fk = infer_relation_table(source_table, target_table, tables)

    extra_values = parse_key_value(args.set_values)
    if args.role is not None:
        extra_values["role"] = args.role

    path = DATA_DIR / f"{relation_table}.csv"
    if path.exists():
        fieldnames, rows = read_table(path)
    else:
        fieldnames = ["id", source_fk, target_fk]
        for key in extra_values:
            if key not in fieldnames:
                fieldnames.append(key)
        rows = []

    for required in ["id", source_fk, target_fk]:
        if required not in fieldnames:
            fieldnames.append(required)
    for key in extra_values:
        if key not in fieldnames:
            fieldnames.append(key)

    for row in rows:
        if (row.get(source_fk) or "").strip() == source_id and (row.get(target_fk) or "").strip() == target_id:
            same_extras = all((row.get(key) or "").strip() == value for key, value in extra_values.items())
            if same_extras:
                print(f"Link already exists in {relation_table}: {source_id} -> {target_id}")
                return 0

    relation_id = args.id or f"{relation_table}_{source_id}_{target_id}"
    existing_ids = {(row.get("id") or "").strip() for row in rows}
    if relation_id in existing_ids:
        raise ValueError(f"relationship id already exists: {relation_id}")

    row = {field: "" for field in fieldnames}
    row["id"] = relation_id
    row[source_fk] = source_id
    row[target_fk] = target_id
    for key, value in extra_values.items():
        row[key] = value
    rows.append(row)
    write_table(path, fieldnames, rows)

    run_automation()
    print(f"Created link in {relation_table}: {relation_id}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GitPKM CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new", help="Create a new entity row and note")
    new_parser.add_argument("entity_type", help="Exact dataset name, for example person, people, program, or programs")
    new_parser.add_argument("name", help="Display name for the entity")
    new_parser.add_argument("--id", help="Override the generated stable ID")
    new_parser.add_argument(
        "--set",
        dest="set_values",
        action="append",
        default=[],
        help="Additional entity field values as key=value",
    )
    new_parser.set_defaults(func=command_new)

    link_parser = subparsers.add_parser("link", help="Create a relationship row between two existing IDs")
    link_parser.add_argument("source_id", help="Existing source entity ID")
    link_parser.add_argument("target_id", help="Existing target entity ID")
    link_parser.add_argument("--table", help="Relationship table name to use or create")
    link_parser.add_argument("--id", help="Override the generated relationship ID")
    link_parser.add_argument("--role", help="Optional role value to store when the relation uses a role column")
    link_parser.add_argument(
        "--set",
        dest="set_values",
        action="append",
        default=[],
        help="Additional field values as key=value",
    )
    link_parser.set_defaults(func=command_link)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        return args.func(args)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
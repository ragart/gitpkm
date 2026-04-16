#!/usr/bin/env python3
"""Minimal CLI for managing PKM CSV entities and relations."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from scripts.automation import build_indexes, generate_pages

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
MAPPINGS_DIR = ROOT / "schema" / "import_mappings"


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


def parse_columns(raw: str) -> List[str]:
    if not raw:
        return []

    columns: List[str] = []
    seen = set()
    for item in raw.split(","):
        col = item.strip()
        if not col:
            continue
        if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", col):
            raise ValueError(f"invalid column name: {col}")
        if col in seen:
            continue
        seen.add(col)
        columns.append(col)
    return columns


def parse_template_tokens(template: str) -> List[str]:
    return re.findall(r"\{([^{}]+)\}", template)


def resolve_mapping_value(spec: str, source_row: Dict[str, str], refs: Dict[str, str]) -> str:
    if spec.startswith("ref:"):
        ref_key = spec[4:].strip()
        if not ref_key:
            raise ValueError("invalid ref mapping value: ref:")
        if ref_key not in refs:
            raise ValueError(f"unknown ref key: {ref_key}")
        return refs[ref_key]

    if spec.startswith("const:"):
        return spec[6:]

    if spec not in source_row:
        raise ValueError(f"unknown source column in mapping: {spec}")
    return (source_row.get(spec) or "").strip()


def render_id_template(template: str, source_row: Dict[str, str], refs: Dict[str, str]) -> str:
    def replacer(match: re.Match[str]) -> str:
        token = match.group(1).strip()
        if token.startswith("slug:"):
            key = token[5:].strip()
            if key not in source_row:
                raise ValueError(f"unknown source column in template: {key}")
            return slugify((source_row.get(key) or "").strip())

        if token.startswith("ref:"):
            ref_key = token[4:].strip()
            if ref_key not in refs:
                raise ValueError(f"unknown ref key in template: {ref_key}")
            return refs[ref_key]

        if token not in source_row:
            raise ValueError(f"unknown source column in template: {token}")
        return slugify((source_row.get(token) or "").strip())

    return re.sub(r"\{([^{}]+)\}", replacer, template)


def ensure_table(
    tables: Dict[str, Tuple[List[str], List[Dict[str, str]]]], table_name: str, columns: List[str]
) -> Tuple[List[str], List[Dict[str, str]]]:
    if table_name in tables:
        fieldnames, rows = tables[table_name]
    else:
        fieldnames, rows = ["id"], []
        tables[table_name] = (fieldnames, rows)

    for column in columns:
        if column not in fieldnames:
            fieldnames.append(column)

    if "id" not in fieldnames:
        fieldnames.insert(0, "id")
    return fieldnames, rows


def upsert_row(fieldnames: List[str], rows: List[Dict[str, str]], values: Dict[str, str]) -> str:
    row_id = (values.get("id") or "").strip()
    if not row_id:
        raise ValueError("row id cannot be empty")

    for key in values:
        if key not in fieldnames:
            fieldnames.append(key)

    existing = None
    for row in rows:
        if (row.get("id") or "").strip() == row_id:
            existing = row
            break

    if existing is None:
        row = {field: "" for field in fieldnames}
        for key, value in values.items():
            row[key] = value
        rows.append(row)
        return "inserted"

    changed = False
    for key, value in values.items():
        old_value = (existing.get(key) or "").strip()
        if old_value != value:
            existing[key] = value
            changed = True

    return "updated" if changed else "unchanged"


def load_json_file(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid mapping JSON in {path}: {exc.msg}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"mapping root must be a JSON object: {path}")
    return data


def validate_mapping(mapping: Dict[str, Any], source_columns: List[str] | None = None) -> None:
    entities = mapping.get("entities")
    relations = mapping.get("relations")
    if not isinstance(entities, list) or not isinstance(relations, list):
        raise ValueError("mapping must define list fields: entities and relations")

    source_set = set(source_columns or [])

    entity_keys = set()
    for entity in entities:
        if not isinstance(entity, dict):
            raise ValueError("each entity mapping must be an object")

        table = (entity.get("table") or "").strip()
        if not table:
            raise ValueError("entity mapping missing table")

        key = (entity.get("key") or table).strip()
        if key in entity_keys:
            raise ValueError(f"duplicate entity key in mapping: {key}")
        entity_keys.add(key)

        name_column = (entity.get("name_column") or "").strip()
        if not name_column:
            raise ValueError(f"entity mapping {key} missing name_column")
        if source_columns is not None and name_column not in source_set:
            raise ValueError(f"unknown name_column for entity {key}: {name_column}")

        id_template = (entity.get("id_template") or "").strip()
        if not id_template:
            raise ValueError(f"entity mapping {key} missing id_template")
        for token in parse_template_tokens(id_template):
            token = token.strip()
            if token.startswith("ref:"):
                ref_key = token[4:].strip()
                if ref_key not in entity_keys:
                    raise ValueError(f"unknown ref in entity id_template for {key}: {ref_key}")
                continue
            source_token = token[5:].strip() if token.startswith("slug:") else token
            if source_columns is not None and source_token not in source_set:
                raise ValueError(f"unknown source token in entity id_template for {key}: {source_token}")

        fields = entity.get("fields") or {}
        if not isinstance(fields, dict):
            raise ValueError(f"entity mapping fields must be an object for {key}")
        for source_spec in fields.values():
            if not isinstance(source_spec, str):
                raise ValueError(f"entity mapping field specs must be strings for {key}")
            if source_spec.startswith(("ref:", "const:")):
                continue
            if source_columns is not None and source_spec not in source_set:
                raise ValueError(f"unknown source column in entity mapping {key}: {source_spec}")

    for relation in relations:
        if not isinstance(relation, dict):
            raise ValueError("each relation mapping must be an object")

        table = (relation.get("table") or "").strip()
        if not table:
            raise ValueError("relation mapping missing table")

        fields = relation.get("fields") or {}
        if not isinstance(fields, dict) or not fields:
            raise ValueError(f"relation mapping fields must be a non-empty object for {table}")
        for source_spec in fields.values():
            if not isinstance(source_spec, str):
                raise ValueError(f"relation mapping field specs must be strings for {table}")
            if source_spec.startswith("ref:"):
                ref_key = source_spec[4:].strip()
                if ref_key not in entity_keys:
                    raise ValueError(f"unknown ref in relation mapping {table}: {ref_key}")
                continue
            if source_spec.startswith("const:"):
                continue
            if source_columns is not None and source_spec not in source_set:
                raise ValueError(f"unknown source column in relation mapping {table}: {source_spec}")

        id_template = (relation.get("id_template") or "").strip()
        if id_template:
            for token in parse_template_tokens(id_template):
                token = token.strip()
                if token.startswith("ref:"):
                    ref_key = token[4:].strip()
                    if ref_key not in entity_keys:
                        raise ValueError(f"unknown ref in relation id_template for {table}: {ref_key}")
                    continue
                source_token = token[5:].strip() if token.startswith("slug:") else token
                if source_columns is not None and source_token not in source_set:
                    raise ValueError(f"unknown source token in relation id_template for {table}: {source_token}")

    match = mapping.get("match")
    if match is not None:
        if not isinstance(match, dict):
            raise ValueError("match must be an object when provided")
        source_cols = match.get("source_columns")
        if source_cols is not None:
            if not isinstance(source_cols, list) or not all(isinstance(item, str) for item in source_cols):
                raise ValueError("match.source_columns must be a list of strings")

    required_columns = mapping.get("required_csv_columns")
    if required_columns is not None:
        if not isinstance(required_columns, list) or not all(isinstance(item, str) for item in required_columns):
            raise ValueError("required_csv_columns must be a list of strings")


def get_mapping_source_columns(mapping: Dict[str, Any]) -> List[str]:
    columns: List[str] = []
    seen = set()

    def add_column(column: str) -> None:
        column = column.strip()
        if not column or column in seen:
            return
        seen.add(column)
        columns.append(column)

    for entity in mapping.get("entities") or []:
        if not isinstance(entity, dict):
            continue
        add_column((entity.get("name_column") or "").strip())
        for source_spec in (entity.get("fields") or {}).values():
            if not isinstance(source_spec, str):
                continue
            if source_spec.startswith(("ref:", "const:")):
                continue
            add_column(source_spec)
        id_template = (entity.get("id_template") or "").strip()
        for token in parse_template_tokens(id_template):
            token = token.strip()
            if token.startswith("ref:"):
                continue
            add_column(token[5:].strip() if token.startswith("slug:") else token)

    for relation in mapping.get("relations") or []:
        if not isinstance(relation, dict):
            continue
        for source_spec in (relation.get("fields") or {}).values():
            if not isinstance(source_spec, str):
                continue
            if source_spec.startswith(("ref:", "const:")):
                continue
            add_column(source_spec)
        id_template = (relation.get("id_template") or "").strip()
        for token in parse_template_tokens(id_template):
            token = token.strip()
            if token.startswith("ref:"):
                continue
            add_column(token[5:].strip() if token.startswith("slug:") else token)

    match = mapping.get("match") or {}
    if isinstance(match, dict):
        for column in match.get("source_columns") or []:
            if isinstance(column, str):
                add_column(column)

    for column in mapping.get("required_csv_columns") or []:
        if isinstance(column, str):
            add_column(column)

    return columns


def mapping_matches_source_columns(mapping: Dict[str, Any], source_columns: List[str]) -> bool:
    required_columns = get_mapping_source_columns(mapping)
    return set(required_columns).issubset(set(source_columns))


def resolve_mapping_path(raw_mapping: str, mappings_dir: Path, source_columns: List[str]) -> Path:
    if raw_mapping and raw_mapping != "auto":
        candidate = Path(raw_mapping).expanduser()
        if candidate.exists():
            return candidate.resolve()

        if not candidate.suffix:
            candidate = mappings_dir / f"{raw_mapping}.json"
        elif not candidate.is_absolute():
            candidate = mappings_dir / candidate.name

        if candidate.exists():
            return candidate.resolve()

        raise ValueError(
            f"mapping file not found: {raw_mapping}; checked {candidate} and the provided path"
        )

    if not mappings_dir.exists():
        raise ValueError(f"mappings directory does not exist: {mappings_dir}")

    candidates = sorted(path for path in mappings_dir.glob("*.json") if path.is_file())
    if not candidates:
        raise ValueError(f"no mapping files found in: {mappings_dir}")

    matching: List[Path] = []
    for path in candidates:
        try:
            mapping = load_json_file(path)
            validate_mapping(mapping)
        except ValueError as exc:
            raise ValueError(f"invalid mapping file {path}: {exc}") from exc
        if mapping_matches_source_columns(mapping, source_columns):
            matching.append(path)

    if not matching:
        available = ", ".join(path.stem for path in candidates) or "none"
        raise ValueError(
            f"no import mapping matched the source columns; available mappings: {available}"
        )
    if len(matching) > 1:
        options = ", ".join(path.stem for path in matching)
        raise ValueError(
            f"multiple import mappings matched the source columns: {options}; use --mapping <name>"
        )

    return matching[0].resolve()


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


def command_reprocess_notes(_: argparse.Namespace) -> int:
    generate_pages.generate()
    print("Reprocessed notes from current CSV tables.")
    return 0


def command_new(args: argparse.Namespace) -> int:
    entity_type = args.entity_type.strip().lower()
    table_name = entity_type
    extra_values = parse_key_value(args.set_values)
    requested_columns = parse_columns(args.columns)
    table_path = DATA_DIR / f"{table_name}.csv"
    table_exists = table_path.exists()

    if table_exists:
        table_path, fieldnames, rows = ensure_entity_table(table_name)
    else:
        fieldnames = ["id", "name"]
        rows = []

    reserved = {"id", "name"}
    invalid_reserved = sorted(reserved.intersection(set(extra_values.keys()).union(requested_columns)))
    if invalid_reserved:
        if "id" in invalid_reserved:
            raise ValueError("do not define id with --set/--columns; use --id")
        raise ValueError("do not define name with --set/--columns; use the <name> positional argument")

    if table_exists:
        unknown_columns = sorted(set(extra_values.keys()).union(requested_columns) - set(fieldnames))
        if unknown_columns:
            allowed_columns = ", ".join(sorted(fieldnames))
            raise ValueError(
                f"unknown columns for {table_name}: {', '.join(unknown_columns)}; allowed columns: {allowed_columns}"
            )
    else:
        for column in requested_columns:
            if column not in fieldnames:
                fieldnames.append(column)
        for column in extra_values:
            if column not in fieldnames:
                fieldnames.append(column)

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


def command_update(args: argparse.Namespace) -> int:
    entity_type = args.entity_type.strip().lower()
    entity_id = args.entity_id.strip()
    updates = parse_key_value(args.set_values)

    if not updates:
        raise ValueError("at least one --set key=value is required")
    if "id" in updates:
        raise ValueError("updating id is not supported")

    table_path = DATA_DIR / f"{entity_type}.csv"
    if not table_path.exists():
        raise ValueError(f"dataset does not exist: {entity_type}")

    table_path, fieldnames, rows = ensure_entity_table(entity_type)

    unknown_columns = sorted(set(updates.keys()) - set(fieldnames))
    if unknown_columns:
        allowed_columns = ", ".join(sorted(fieldnames))
        raise ValueError(
            f"unknown columns for {entity_type}: {', '.join(unknown_columns)}; allowed columns: {allowed_columns}"
        )

    target_row = None
    for row in rows:
        if (row.get("id") or "").strip() == entity_id:
            target_row = row
            break

    if target_row is None:
        raise ValueError(f"entity id not found in {entity_type}: {entity_id}")

    changed = False
    for key, value in updates.items():
        old_value = (target_row.get(key) or "").strip()
        if old_value != value:
            target_row[key] = value
            changed = True

    if not changed:
        print(f"No changes for {entity_type}: {entity_id}")
        return 0

    write_table(table_path, fieldnames, rows)
    run_automation()
    print(f"Updated {entity_type}: {entity_id}")
    return 0


def command_bulk_import(args: argparse.Namespace) -> int:
    source_path = Path(args.input).expanduser().resolve()
    mappings_dir = Path(args.mappings_dir).expanduser().resolve()

    if not source_path.exists():
        raise ValueError(f"input file does not exist: {source_path}")

    with source_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        source_rows = list(reader)
        source_columns = reader.fieldnames or []

    if not source_columns:
        raise ValueError("input CSV must include a header row")

    mapping_path = resolve_mapping_path(args.mapping, mappings_dir, source_columns)
    mapping = load_json_file(mapping_path)
    validate_mapping(mapping, source_columns)

    try:
        mapping_display = mapping_path.relative_to(ROOT)
    except ValueError:
        mapping_display = mapping_path
    print(f"Using mapping: {mapping_display}")

    entities = mapping.get("entities") or []
    relations = mapping.get("relations") or []

    if getattr(args, "validate_only", False):
        print("Mapping and source CSV are valid. No rows were processed.")
        return 0

    tables = load_tables()
    counts: Dict[str, Dict[str, int]] = {}

    for row_number, source_row in enumerate(source_rows, start=2):
        refs: Dict[str, str] = {}

        try:
            for entity in entities:
                table = entity["table"].strip()
                key = (entity.get("key") or table).strip()
                id_template = entity["id_template"].strip()
                name_column = entity["name_column"].strip()
                fields = entity.get("fields") or {}

                entity_id = render_id_template(id_template, source_row, refs)
                name_value = (source_row.get(name_column) or "").strip()
                if not name_value:
                    raise ValueError(f"empty name value for entity {key} at source column {name_column}")

                values = {"id": entity_id, "name": name_value}
                for target_column, source_spec in fields.items():
                    values[target_column] = resolve_mapping_value(source_spec, source_row, refs)

                fieldnames, rows = ensure_table(tables, table, list(values.keys()))
                status = upsert_row(fieldnames, rows, values)
                refs[key] = entity_id

                if table not in counts:
                    counts[table] = {"inserted": 0, "updated": 0, "unchanged": 0}
                counts[table][status] += 1

            for relation in relations:
                table = relation["table"].strip()
                fields = relation["fields"]
                id_template = (relation.get("id_template") or "").strip()

                values: Dict[str, str] = {}
                for target_column, source_spec in fields.items():
                    values[target_column] = resolve_mapping_value(source_spec, source_row, refs)

                if id_template:
                    relation_id = render_id_template(id_template, source_row, refs)
                else:
                    signature_cols = [col for col in fields if col.endswith("_id")]
                    signature_values = [values[col] for col in signature_cols if values.get(col)]
                    signature = "_".join(signature_values)
                    relation_id = f"{table}_{signature}" if signature else f"{table}_{row_number}"

                values["id"] = relation_id

                fieldnames, rows = ensure_table(tables, table, list(values.keys()))
                status = upsert_row(fieldnames, rows, values)

                if table not in counts:
                    counts[table] = {"inserted": 0, "updated": 0, "unchanged": 0}
                counts[table][status] += 1
        except ValueError as exc:
            raise ValueError(f"row {row_number}: {exc}") from exc

    changed = False
    for table_counts in counts.values():
        if table_counts["inserted"] > 0 or table_counts["updated"] > 0:
            changed = True
            break

    if args.apply:
        if changed:
            for table_name, (fieldnames, rows) in tables.items():
                write_table(DATA_DIR / f"{table_name}.csv", fieldnames, rows)
            run_automation()
            print("Applied bulk import changes.")
        else:
            print("No data changes to apply.")
    else:
        print("Dry-run complete. No files were written.")

    if not counts:
        print("No mapping rows were processed.")
        return 0

    for table_name in sorted(counts):
        table_counts = counts[table_name]
        print(
            f"{table_name}: inserted={table_counts['inserted']}, "
            f"updated={table_counts['updated']}, unchanged={table_counts['unchanged']}"
        )

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


def command_mappings_list(args: argparse.Namespace) -> int:
    mappings_dir = Path(args.mappings_dir).expanduser().resolve()
    if not mappings_dir.exists():
        raise ValueError(f"mappings directory does not exist: {mappings_dir}")

    candidates = sorted(path for path in mappings_dir.glob("*.json") if path.is_file())
    if not candidates:
        print(f"No mappings found in {mappings_dir}")
        return 0

    for path in candidates:
        name = path.stem
        try:
            mapping = load_json_file(path)
            validate_mapping(mapping)
            required = get_mapping_source_columns(mapping)
            required_text = ", ".join(required) if required else "(none)"
            print(f"{name}: valid | required source columns: {required_text}")
        except ValueError as exc:
            print(f"{name}: invalid | {exc}")

    return 0


def command_mappings_validate(args: argparse.Namespace) -> int:
    mappings_dir = Path(args.mappings_dir).expanduser().resolve()
    source_columns: List[str] | None = None

    if args.input:
        source_path = Path(args.input).expanduser().resolve()
        if not source_path.exists():
            raise ValueError(f"input file does not exist: {source_path}")

        with source_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            source_columns = reader.fieldnames or []

        if not source_columns:
            raise ValueError("input CSV must include a header row")

    if args.mapping == "auto":
        if source_columns is None:
            raise ValueError("--mapping auto requires --input so the source header can be matched")
        mapping_path = resolve_mapping_path(args.mapping, mappings_dir, source_columns)
    else:
        mapping_path = resolve_mapping_path(args.mapping, mappings_dir, source_columns or [])

    mapping = load_json_file(mapping_path)
    validate_mapping(mapping, source_columns)

    try:
        mapping_display = mapping_path.relative_to(ROOT)
    except ValueError:
        mapping_display = mapping_path

    if source_columns is None:
        print(f"Mapping is valid: {mapping_display}")
    else:
        print(f"Mapping and source CSV are compatible: {mapping_display}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GitPKM CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new", help="Create a new entity row and note")
    new_parser.add_argument("entity_type", help="Exact dataset name, for example person, people, program, or programs")
    new_parser.add_argument("name", help="Display name for the entity")
    new_parser.add_argument("--id", help="Override the generated stable ID")
    new_parser.add_argument(
        "--columns",
        default="",
        help="Comma-separated columns to create when the dataset does not exist yet",
    )
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

    update_parser = subparsers.add_parser("update", help="Update an existing entity row by ID")
    update_parser.add_argument("entity_type", help="Exact dataset name, for example people or game_disc")
    update_parser.add_argument("entity_id", help="Existing entity ID in that dataset")
    update_parser.add_argument(
        "--set",
        dest="set_values",
        action="append",
        required=True,
        help="Field value update as key=value (repeatable)",
    )
    update_parser.set_defaults(func=command_update)

    mappings_parser = subparsers.add_parser("mappings", help="List and validate bulk-import mappings")
    mappings_subparsers = mappings_parser.add_subparsers(dest="mappings_command", required=True)

    mappings_list_parser = mappings_subparsers.add_parser("list", help="List available mapping files")
    mappings_list_parser.add_argument(
        "--mappings-dir",
        default=str(MAPPINGS_DIR),
        help="Directory containing reusable import mapping JSON files",
    )
    mappings_list_parser.set_defaults(func=command_mappings_list)

    mappings_validate_parser = mappings_subparsers.add_parser("validate", help="Validate one mapping")
    mappings_validate_parser.add_argument(
        "--mapping",
        required=True,
        help="Mapping name, mapping file path, or auto (auto requires --input)",
    )
    mappings_validate_parser.add_argument(
        "--input",
        help="Optional source CSV path to validate mapping compatibility against real headers",
    )
    mappings_validate_parser.add_argument(
        "--mappings-dir",
        default=str(MAPPINGS_DIR),
        help="Directory containing reusable import mapping JSON files",
    )
    mappings_validate_parser.set_defaults(func=command_mappings_validate)

    bulk_parser = subparsers.add_parser(
        "bulk-import",
        help="Import rows from a CSV file using a reusable JSON mapping",
    )
    bulk_parser.add_argument(
        "--input",
        required=True,
        help="Source CSV file path to import",
    )
    bulk_parser.add_argument(
        "--mapping",
        default="auto",
        help="Mapping name, mapping file path, or auto to pick a unique match from the mappings directory",
    )
    bulk_parser.add_argument(
        "--mappings-dir",
        default=str(MAPPINGS_DIR),
        help="Directory containing reusable import mapping JSON files",
    )
    bulk_parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes to data/*.csv and run automation (default is dry-run)",
    )
    bulk_parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate mapping and source CSV compatibility only; do not process rows",
    )
    bulk_parser.set_defaults(func=command_bulk_import)

    reprocess_notes_parser = subparsers.add_parser(
        "reprocess-notes",
        help="Re-render generated note headers and blocks from current CSV tables",
    )
    reprocess_notes_parser.set_defaults(func=command_reprocess_notes)

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
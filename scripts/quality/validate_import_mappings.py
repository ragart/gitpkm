#!/usr/bin/env python3
"""Validate import mappings against the repository contract.

This script is intentionally lightweight so CI can enforce the mapping format
without adding a third-party JSON Schema dependency.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pkm

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA = ROOT / "schema" / "import_mapping.contract.schema.json"
DEFAULT_MAPPINGS_DIR = ROOT / "schema" / "import_mappings"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def validate_contract_schema(schema: dict) -> None:
    required_keys = {"$schema", "$id", "title", "type", "additionalProperties", "required", "properties", "$defs"}
    missing = sorted(required_keys - set(schema))
    if missing:
        raise ValueError(f"contract schema missing keys: {', '.join(missing)}")

    if schema.get("type") != "object":
        raise ValueError("contract schema must declare type=object")
    if schema.get("additionalProperties") is not False:
        raise ValueError("contract schema must disable additionalProperties")

    required = schema.get("required")
    if required != ["entities", "relations"]:
        raise ValueError("contract schema must require entities and relations")


def validate_mapping_directory(mappings_dir: Path) -> None:
    if not mappings_dir.exists():
        return

    mapping_files = sorted(path for path in mappings_dir.glob("*.json") if path.is_file())
    for path in mapping_files:
        mapping = pkm.load_json_file(path)
        pkm.validate_mapping(mapping)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate GitPKM import mappings")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA), help="Path to the mapping contract schema")
    parser.add_argument(
        "--mappings-dir",
        default=str(DEFAULT_MAPPINGS_DIR),
        help="Directory containing reusable import mapping JSON files",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    schema_path = Path(args.schema).expanduser().resolve()
    mappings_dir = Path(args.mappings_dir).expanduser().resolve()

    try:
        schema = load_json(schema_path)
        validate_contract_schema(schema)
        validate_mapping_directory(mappings_dir)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Validated mapping contract: {schema_path.relative_to(ROOT)}")
    print(f"Validated mapping directory: {mappings_dir.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
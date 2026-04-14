#!/usr/bin/env python3
"""Process GitHub issue form submissions into PKM CLI operations."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[2]

NO_RESPONSE_TOKENS = {
    "",
    "_no response_",
    "n/a",
    "na",
    "none",
}


def parse_issue_sections(body: str) -> Dict[str, str]:
    sections: Dict[str, List[str]] = {}
    current: str | None = None

    for raw_line in body.splitlines():
        line = raw_line.rstrip("\n")
        match = re.match(r"^###\s+(.+?)\s*$", line)
        if match:
            current = match.group(1).strip()
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)

    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def normalize_value(value: str) -> str:
    normalized = value.strip()
    if normalized.lower() in NO_RESPONSE_TOKENS:
        return ""
    return normalized


def parse_kv_lines(raw_value: str) -> List[str]:
    value = normalize_value(raw_value)
    if not value:
        return []

    pairs: List[str] = []
    for line in value.splitlines():
        item = line.strip()
        if not item:
            continue
        if item.startswith("- "):
            item = item[2:].strip()
        if "=" not in item:
            raise ValueError(f"invalid key=value pair in additional fields: {item}")
        key, val = item.split("=", 1)
        if not key.strip():
            raise ValueError(f"invalid key=value pair in additional fields: {item}")
        pairs.append(f"{key.strip()}={val.strip()}")
    return pairs


def required(sections: Dict[str, str], key: str) -> str:
    value = normalize_value(sections.get(key, ""))
    if not value:
        raise ValueError(f"missing required field in issue form: {key}")
    return value


def optional(sections: Dict[str, str], key: str) -> str:
    return normalize_value(sections.get(key, ""))


def build_entity_command(sections: Dict[str, str]) -> List[str]:
    dataset = required(sections, "Dataset")
    name = required(sections, "Entity Name")
    entity_id = optional(sections, "Entity ID (Optional)")
    dataset_columns = optional(sections, "Dataset Columns (Optional)")
    extra_pairs = parse_kv_lines(sections.get("Additional Fields (Optional)", ""))

    cmd = [sys.executable, "pkm.py", "new", dataset, name]
    if entity_id:
        cmd.extend(["--id", entity_id])
    if dataset_columns:
        cmd.extend(["--columns", dataset_columns])
    for pair in extra_pairs:
        cmd.extend(["--set", pair])
    return cmd


def build_link_command(sections: Dict[str, str]) -> List[str]:
    source_id = required(sections, "Source ID")
    target_id = required(sections, "Target ID")
    relation_table = optional(sections, "Relationship Table (Optional)")
    relation_id = optional(sections, "Relationship ID (Optional)")
    role = optional(sections, "Role (Optional)")
    extra_pairs = parse_kv_lines(sections.get("Additional Fields (Optional)", ""))

    cmd = [sys.executable, "pkm.py", "link", source_id, target_id]
    if relation_table:
        cmd.extend(["--table", relation_table])
    if relation_id:
        cmd.extend(["--id", relation_id])
    if role:
        cmd.extend(["--role", role])
    for pair in extra_pairs:
        cmd.extend(["--set", pair])
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(description="Process PKM GitHub issue forms")
    parser.add_argument("--mode", choices=["entity", "link"], required=True)
    parser.add_argument("--body-file", required=True, help="Path to issue body markdown file")
    args = parser.parse_args()

    body_path = Path(args.body_file)
    body = body_path.read_text(encoding="utf-8")
    sections = parse_issue_sections(body)

    if args.mode == "entity":
        cmd = build_entity_command(sections)
    else:
        cmd = build_link_command(sections)

    print("Running command:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
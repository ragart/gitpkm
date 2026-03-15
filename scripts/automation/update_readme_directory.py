#!/usr/bin/env python3
"""Render a directory-style README when data and indexes are available."""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
NOTES_DIR = ROOT / "notes"
README_PATH = ROOT / "README.md"


def read_csv_inventory(path: Path) -> Tuple[int, int]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        columns = len(reader.fieldnames or [])
        rows = sum(1 for _ in reader)
    return rows, columns


def collect_dataset_inventory(data_dir: Path) -> List[Tuple[str, int, int]]:
    if not data_dir.exists():
        return []

    inventory: List[Tuple[str, int, int]] = []
    for csv_path in sorted(data_dir.glob("*.csv")):
        rows, columns = read_csv_inventory(csv_path)
        inventory.append((csv_path.name, rows, columns))
    return inventory


def has_non_empty_data(data_dir: Path) -> bool:
    return any(rows > 0 for _, rows, _ in collect_dataset_inventory(data_dir))


def extract_first_h1(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("_", " ").title()


def infer_index_kind(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if "\n| " in text and "\n| ---" in text:
        return "entity_table"
    if re.search(r"^\s*-\s+\[", text, flags=re.MULTILINE):
        return "entity_list"
    return "unknown"


def collect_index_inventory(notes_dir: Path) -> List[Tuple[str, str, str]]:
    index_dir = notes_dir / "indexes"
    if not index_dir.exists():
        return []

    inventory: List[Tuple[str, str, str]] = []
    for index_path in sorted(index_dir.glob("*.md")):
        rel = index_path.relative_to(index_dir).as_posix()
        inventory.append((rel, extract_first_h1(index_path), infer_index_kind(index_path)))
    return inventory


def collect_note_directories(notes_dir: Path) -> List[Tuple[str, int]]:
    if not notes_dir.exists():
        return []

    counts: Dict[str, int] = {}
    for note in sorted(notes_dir.rglob("*.md")):
        rel = note.relative_to(notes_dir)
        if rel.parts[:1] == ("indexes",):
            continue
        folder = rel.parent.as_posix()
        if folder == ".":
            folder = "(root)"
        counts[folder] = counts.get(folder, 0) + 1

    return sorted(counts.items())


def build_readme_content(root: Path) -> str:
    datasets = collect_dataset_inventory(root / "data")
    indexes = collect_index_inventory(root / "notes")
    note_dirs = collect_note_directories(root / "notes")

    lines = [
        "<!-- GENERATED START: directory_readme -->",
        "# Knowledge Directory",
        "",
        "Directory-style overview generated from current data and indexes.",
        "",
        "## Quick Navigation",
        "",
        "- [data/](data/)",
        "- [notes/](notes/)",
        "- [notes/indexes/](notes/indexes/)",
        "- [schema/](schema/)",
        "",
        "## Dataset Inventory",
        "",
        "| Dataset | Rows | Columns |",
        "| --- | ---: | ---: |",
    ]

    for dataset, rows, columns in datasets:
        lines.append(f"| [{dataset}](data/{dataset}) | {rows} | {columns} |")

    lines.extend(
        [
            "",
            "## Index Pages",
            "",
            "| Index file | Title | Type |",
            "| --- | --- | --- |",
        ]
    )

    for index_file, title, kind in indexes:
        lines.append(f"| [{index_file}](notes/indexes/{index_file}) | {title} | {kind} |")

    lines.extend(
        [
            "",
            "## Note Directories",
            "",
            "| Folder | Notes |",
            "| --- | ---: |",
        ]
    )

    for folder, count in note_dirs:
        if folder == "(root)":
            lines.append(f"| {folder} | {count} |")
        else:
            lines.append(f"| [{folder}/](notes/{folder}/) | {count} |")

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "Generated content only. Edit source data and rerun automation to update.",
            "",
            "<!-- GENERATED END -->",
            "",
        ]
    )

    return "\n".join(lines)


def write_if_changed(path: Path, content: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def update_readme(root: Path = ROOT) -> bool:
    data_dir = root / "data"
    notes_dir = root / "notes"

    if not has_non_empty_data(data_dir):
        return False

    if not collect_index_inventory(notes_dir):
        return False

    return write_if_changed(root / "README.md", build_readme_content(root))


def main() -> int:
    changed = update_readme(ROOT)
    print(f"README directory updated: {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

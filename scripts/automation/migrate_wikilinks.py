#!/usr/bin/env python3
"""Rewrite wiki-style links ([[id]]) to relative Markdown links.

Behavior:
- Scans notes/**/*.md by default (including notes/indexes)
- Converts [[id]] -> [id](relative/path/to/id.md) when id can be resolved
- Leaves unresolved wiki links unchanged
"""

from __future__ import annotations

import argparse
import csv
import posixpath
import re
from pathlib import Path
from typing import Dict, Iterable, Tuple

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
NOTES_DIR = ROOT / "notes"
WIKI_LINK_RE = re.compile(r"\[\[([a-zA-Z0-9_\-]+)\]\]")


def read_csv(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def load_entity_note_targets() -> Dict[str, Path]:
    targets: Dict[str, Path] = {}

    if DATA_DIR.exists():
        for csv_path in sorted(DATA_DIR.glob("*.csv")):
            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                columns = reader.fieldnames or []
                if "id" not in columns or "name" not in columns:
                    continue
                table_name = csv_path.stem
                for row in reader:
                    entity_id = (row.get("id") or "").strip()
                    if not entity_id:
                        continue
                    targets[entity_id] = NOTES_DIR / table_name / f"{entity_id}.md"

    if NOTES_DIR.exists():
        for note_path in sorted(NOTES_DIR.rglob("*.md")):
            targets.setdefault(note_path.stem, note_path)

    return targets


def build_relative_markdown_link(from_note: Path, target_note: Path, label: str) -> str:
    rel = posixpath.relpath(target_note.as_posix(), start=from_note.parent.as_posix())
    return f"[{label}]({rel})"


def rewrite_wikilinks(text: str, from_note: Path, targets: Dict[str, Path]) -> Tuple[str, int]:
    changes = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal changes
        link_id = match.group(1)
        target = targets.get(link_id)
        if not target:
            return match.group(0)

        replacement = build_relative_markdown_link(from_note, target, link_id)
        if replacement != match.group(0):
            changes += 1
        return replacement

    return WIKI_LINK_RE.sub(repl, text), changes


def migrate(target_dir: Path = NOTES_DIR) -> Tuple[int, int]:
    if not target_dir.exists():
        return 0, 0

    targets = load_entity_note_targets()
    files_changed = 0
    links_rewritten = 0

    for note_path in sorted(target_dir.rglob("*.md")):
        text = note_path.read_text(encoding="utf-8")
        rewritten, link_changes = rewrite_wikilinks(text, note_path, targets)
        if link_changes == 0:
            continue

        note_path.write_text(rewritten, encoding="utf-8")
        files_changed += 1
        links_rewritten += link_changes

    return files_changed, links_rewritten


def main() -> int:
    parser = argparse.ArgumentParser(description="Rewrite [[id]] links to relative Markdown links")
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=NOTES_DIR,
        help="Directory containing markdown notes to migrate",
    )
    args = parser.parse_args()

    files_changed, links_rewritten = migrate(args.target_dir)
    print(f"Migrated wiki links: files_changed={files_changed}, links_rewritten={links_rewritten}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

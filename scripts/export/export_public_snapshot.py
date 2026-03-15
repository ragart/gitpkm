#!/usr/bin/env python3
"""Create a public-safe snapshot of the PKM repository.

Behavior:
- Reads private IDs from export/private_ids.txt
- Exports filtered CSV data and notes into public-export/
- Drops rows whose id is private or whose foreign key references a private id
- Skips notes/indexes in export output so indexes can be regenerated
"""

from __future__ import annotations

import argparse
import csv
import fnmatch
import importlib.util
import posixpath
import re
import shutil
from pathlib import Path
from typing import Dict, List, Set

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
NOTES_DIR = ROOT / "notes"
DEFAULT_PRIVATE_IDS = ROOT / "export" / "private_ids.txt"
DEFAULT_PRIVATE_FILES = ROOT / "export" / "private_files.txt"
WIKI_LINK_RE = re.compile(r"\[\[([a-zA-Z0-9_\-]+)\]\]")
MD_LINK_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)|\[[^\]]+\]\(([^)]+)\)")


def generate_indexes_for_export(out_root: Path) -> int:
    module_path = ROOT / "scripts" / "automation" / "build_indexes.py"
    if not module_path.exists():
        return 0

    spec = importlib.util.spec_from_file_location("gitpkm_build_indexes", module_path)
    if spec is None or spec.loader is None:
        return 0

    build_indexes = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_indexes)

    old_root = build_indexes.ROOT
    old_data = build_indexes.DATA_DIR
    old_index = build_indexes.INDEX_DIR
    old_config = build_indexes.AUTOMATION_CONFIG

    try:
        build_indexes.ROOT = out_root
        build_indexes.DATA_DIR = out_root / "data"
        build_indexes.INDEX_DIR = out_root / "notes" / "indexes"
        build_indexes.AUTOMATION_CONFIG = out_root / "schema" / "automation.json"
        code = build_indexes.main()
    finally:
        build_indexes.ROOT = old_root
        build_indexes.DATA_DIR = old_data
        build_indexes.INDEX_DIR = old_index
        build_indexes.AUTOMATION_CONFIG = old_config

    if code != 0:
        return 0

    index_dir = out_root / "notes" / "indexes"
    if not index_dir.exists():
        return 0
    return len(list(index_dir.glob("*.md")))


def read_private_ids(path: Path) -> Set[str]:
    if not path.exists():
        return set()

    ids: Set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        ids.add(line)
    return ids


def read_private_file_patterns(path: Path) -> List[str]:
    if not path.exists():
        return []

    patterns: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def should_drop_row(row: Dict[str, str], private_ids: Set[str]) -> bool:
    row_id = (row.get("id") or "").strip()
    if row_id and row_id in private_ids:
        return True

    for key, value in row.items():
        if key.endswith("_id") and (value or "").strip() in private_ids:
            return True

    return False


def export_csvs(private_ids: Set[str], out_data_dir: Path) -> None:
    out_data_dir.mkdir(parents=True, exist_ok=True)
    for csv_path in sorted(DATA_DIR.glob("*.csv")):
        with csv_path.open("r", encoding="utf-8", newline="") as src:
            reader = csv.DictReader(src)
            fieldnames = reader.fieldnames or []
            rows = [row for row in reader if not should_drop_row(row, private_ids)]

        out_path = out_data_dir / csv_path.name
        with out_path.open("w", encoding="utf-8", newline="") as dst:
            writer = csv.DictWriter(dst, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


def parse_note_frontmatter_id(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    block = text[4:end]
    for line in block.splitlines():
        if line.startswith("id:"):
            return line.split(":", 1)[1].strip() or None
    return None


def sanitize_note_text(text: str, private_ids: Set[str]) -> str:
    def replace_link(match: re.Match[str]) -> str:
        link_id = match.group(1)
        if link_id in private_ids:
            return "[redacted]"
        return match.group(0)

    return WIKI_LINK_RE.sub(replace_link, text)


def note_has_private_references(text: str, private_ids: Set[str]) -> bool:
    for link_id in WIKI_LINK_RE.findall(text):
        if link_id in private_ids:
            return True
    return False


def is_private_file(rel_path: Path, private_patterns: List[str]) -> bool:
    rel = rel_path.as_posix()
    for pattern in private_patterns:
        if fnmatch.fnmatch(rel, pattern):
            return True
    return False


def iter_local_markdown_targets(text: str) -> List[str]:
    targets: List[str] = []
    for match in MD_LINK_RE.finditer(text):
        raw = (match.group(1) or match.group(2) or "").strip()
        if not raw:
            continue

        if raw.startswith("<") and raw.endswith(">"):
            raw = raw[1:-1].strip()

        raw = raw.split()[0]

        lowered = raw.lower()
        if lowered.startswith("http://") or lowered.startswith("https://"):
            continue
        if lowered.startswith("mailto:") or raw.startswith("#") or raw.startswith("/"):
            continue

        targets.append(raw)
    return targets


def export_notes(private_ids: Set[str], out_notes_dir: Path, note_policy: str = "redact") -> None:
    for note in sorted(NOTES_DIR.rglob("*.md")):
        rel = note.relative_to(NOTES_DIR)

        # Indexes are regenerated from exported CSVs and can leak references.
        if rel.parts[:1] == ("indexes",):
            continue

        note_id = parse_note_frontmatter_id(note) or note.stem
        if note_id in private_ids:
            continue

        out_path = out_notes_dir / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        text = note.read_text(encoding="utf-8")
        if note_policy == "drop" and note_has_private_references(text, private_ids):
            continue

        if note_policy == "redact":
            text = sanitize_note_text(text, private_ids)

        out_path.write_text(text, encoding="utf-8")


def export_note_assets(out_notes_dir: Path, private_patterns: List[str]) -> int:
    copied = 0
    for exported_note in sorted(out_notes_dir.rglob("*.md")):
        rel_note = exported_note.relative_to(out_notes_dir)
        note_dir = rel_note.parent
        text = exported_note.read_text(encoding="utf-8")

        for target in iter_local_markdown_targets(text):
            rel_target = Path(posixpath.normpath((note_dir / target).as_posix()))
            if not rel_target.parts or rel_target.parts[0] == "..":
                continue
            if rel_target.suffix.lower() == ".md":
                continue
            if rel_target.parts[:1] == ("indexes",):
                continue
            if is_private_file(rel_target, private_patterns):
                continue

            source_path = NOTES_DIR / rel_target
            if not source_path.exists() or not source_path.is_file():
                continue

            destination = out_notes_dir / rel_target
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination)
            copied += 1

    return copied


def copy_docs(out_root: Path) -> None:
    for candidate in [ROOT / "README.md", ROOT / "schema"]:
        if not candidate.exists():
            continue
        dest = out_root / candidate.name
        if candidate.is_dir():
            shutil.copytree(candidate, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(candidate, dest)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export public-safe PKM snapshot")
    parser.add_argument(
        "--private-ids",
        type=Path,
        default=DEFAULT_PRIVATE_IDS,
        help="Path to file listing private IDs",
    )
    parser.add_argument(
        "--private-files",
        type=Path,
        default=DEFAULT_PRIVATE_FILES,
        help="Path to file listing private note file patterns to exclude from exported attachments",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "public-export",
        help="Output directory",
    )
    parser.add_argument(
        "--note-policy",
        choices=["redact", "drop"],
        default="redact",
        help="How to handle notes that reference private IDs: redact links or drop the note",
    )
    args = parser.parse_args()

    private_ids = read_private_ids(args.private_ids)
    private_file_patterns = read_private_file_patterns(args.private_files)
    output_dir = args.output

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    export_csvs(private_ids, output_dir / "data")
    out_notes_dir = output_dir / "notes"
    export_notes(private_ids, out_notes_dir, note_policy=args.note_policy)
    copied_assets = export_note_assets(out_notes_dir, private_file_patterns)
    copy_docs(output_dir)
    generated_indexes = generate_indexes_for_export(output_dir)
    print(
        f"Export complete: {output_dir} (private ids filtered: {len(private_ids)}, private file patterns: {len(private_file_patterns)}, note policy: {args.note_policy}, assets copied: {copied_assets}, indexes: {generated_indexes})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

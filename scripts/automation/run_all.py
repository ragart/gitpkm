#!/usr/bin/env python3
"""Run the full GitPKM automation pipeline."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"

PIPELINE = [
    Path("automation/generate_pages.py"),
    Path("automation/build_indexes.py"),
    Path("automation/update_readme_directory.py"),
    Path("quality/validate.py"),
]


def run_script(script_rel_path: Path) -> int:
    script_path = SCRIPTS_DIR / script_rel_path
    if not script_path.exists():
        print(f"missing script: {script_path.relative_to(ROOT)}")
        return 1

    cmd = [sys.executable, str(script_path)]
    print(f"> Running: {' '.join(cmd)}")
    completed = subprocess.run(cmd, cwd=str(ROOT), check=False)
    return completed.returncode


def main() -> int:
    for script_rel_path in PIPELINE:
        code = run_script(script_rel_path)
        if code != 0:
            print(f"Pipeline failed at {script_rel_path} (exit code {code}).")
            return code

    print("Pipeline completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

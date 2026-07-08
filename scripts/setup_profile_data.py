#!/usr/bin/env python3
"""Copy example profile files into data/ if local copies are missing."""

from __future__ import annotations

import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

COPY_MAP = {
    "candidate_profile.example.yaml": "candidate_profile.yaml",
    "resume.example.md": "resume.md",
    "standard_answers.example.yaml": "standard_answers.yaml",
    "interview_stories.example.yaml": "interview_stories.yaml",
    "missing_data.example.yaml": "missing_data.yaml",
}


def main() -> None:
    created: list[str] = []
    skipped: list[str] = []

    for source_name, target_name in COPY_MAP.items():
        source = DATA_DIR / source_name
        target = DATA_DIR / target_name

        if not source.exists():
            print(f"[skip] missing template: {source_name}")
            continue

        if target.exists():
            skipped.append(target_name)
            continue

        shutil.copy2(source, target)
        created.append(target_name)

    if created:
        print("Created:")
        for name in created:
            print(f"  - data/{name}")
    else:
        print("No new files created.")

    if skipped:
        print("Already present (not overwritten):")
        for name in skipped:
            print(f"  - data/{name}")

    print("\nEdit files in data/ with your real profile before using the agent.")


if __name__ == "__main__":
    main()

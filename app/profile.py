import re

import yaml
from pathlib import Path

from app.config import DATA_DIR, PROMPTS_DIR

_PROMPT_NAME = re.compile(r"^[a-z0-9_]+$")


class ProfileDataError(Exception):
    """Raised when profile data files are missing or invalid."""


def _resolve_data_path(filename: str) -> Path:
    primary = DATA_DIR / filename
    if primary.exists():
        return primary

    if filename.endswith(".yaml"):
        example = DATA_DIR / filename.replace(".yaml", ".example.yaml")
    elif filename.endswith(".md"):
        example = DATA_DIR / filename.replace(".md", ".example.md")
    else:
        example = DATA_DIR / f"{filename}.example"

    if example.exists():
        return example

    return primary


def load_yaml(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except FileNotFoundError as exc:
        raise ProfileDataError(
            f"Missing data file: {path.name}. "
            "Copy the matching file from data/*.example.* or run: "
            "python scripts/setup_profile_data.py"
        ) from exc
    except yaml.YAMLError as exc:
        raise ProfileDataError(f"Invalid YAML in {path.name}: {exc}") from exc
    return data or {}


def load_text(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8") as file:
            return file.read().strip()
    except FileNotFoundError as exc:
        raise ProfileDataError(f"Missing file: {path.name}") from exc


def format_for_prompt(value: dict | list | str | None) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return yaml.dump(
        value,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).strip()


def load_candidate_profile() -> dict:
    return load_yaml(_resolve_data_path("candidate_profile.yaml"))


def load_standard_answers() -> dict:
    return load_yaml(_resolve_data_path("standard_answers.yaml"))


def load_interview_stories() -> dict:
    return load_yaml(_resolve_data_path("interview_stories.yaml"))


def load_missing_data() -> dict:
    return load_yaml(_resolve_data_path("missing_data.yaml"))


def load_resume() -> str:
    return load_text(_resolve_data_path("resume.md"))


def load_prompt(name: str) -> str:
    if not _PROMPT_NAME.match(name):
        raise ProfileDataError(f"Invalid prompt name: {name}")
    return load_text(PROMPTS_DIR / f"{name}.md")


def trim_job_text(job_text: str, max_chars: int = 6000) -> str:
    text = job_text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[Job description truncated for faster processing]"

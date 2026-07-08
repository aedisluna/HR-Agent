import yaml
from pathlib import Path

from app.config import DATA_DIR, PROMPTS_DIR


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
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def load_text(path: Path) -> str:
    with path.open("r", encoding="utf-8") as file:
        return file.read().strip()


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
    return load_text(PROMPTS_DIR / f"{name}.md")


def trim_job_text(job_text: str, max_chars: int = 6000) -> str:
    text = job_text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[Job description truncated for faster processing]"

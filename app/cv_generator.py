import json
import re

from app.config import JOB_TEXT_MAX_CHARS, MODEL_CV
from app.language import language_instruction, resolve_language
from app.llm import ask_llm
from app.memory import candidate_context_for_query
from app.profile import load_prompt, trim_job_text

_HH_MARKDOWN_PATTERNS = (
    (re.compile(r"^#{1,6}\s+", re.MULTILINE), ""),
    (re.compile(r"\*\*([^*]+)\*\*"), r"\1"),
    (re.compile(r"^---+\s*$", re.MULTILINE), ""),
    (re.compile(r"^[*-]\s+", re.MULTILINE), ""),
)


def _strip_markdown(text: str) -> str:
    cleaned = text.strip()
    for pattern, replacement in _HH_MARKDOWN_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _cv_prompt_name(platform: str | None) -> str:
    normalized = (platform or "").lower()
    if normalized == "hh":
        return "tailored_cv_hh"
    if normalized == "linkedin":
        return "tailored_cv_linkedin"
    return "tailored_cv"


def _cv_generation_options(prompt_name: str) -> tuple[int, bool, str | None]:
    if prompt_name == "tailored_cv_hh":
        return 1400, True, None
    if prompt_name == "tailored_cv_linkedin":
        return 2200, False, "en"
    return 2000, False, None


def _cv_user_instructions(prompt_name: str) -> str:
    if prompt_name == "tailored_cv_hh":
        return (
            "Generate a hh.ru cover letter (сопроводительное письмо) for this vacancy. "
            "It complements the attached resume — do not duplicate it. "
            "Use only confirmed profile and resume facts."
        )
    if prompt_name == "tailored_cv_linkedin":
        return (
            "Generate a tailored ATS resume text for LinkedIn Easy Apply. "
            "Use only confirmed profile and resume facts."
        )
    return (
        "Generate a tailored CV/resume text for this vacancy. "
        "Use only confirmed profile and resume facts."
    )


def generate_tailored_cv(
    job_text: str,
    company: str | None = None,
    role: str | None = None,
    response_language: str = "auto",
    platform: str | None = None,
    job_analysis: dict | None = None,
) -> str:
    prompt_name = _cv_prompt_name(platform)
    system_prompt = load_prompt(prompt_name)
    trimmed_job = trim_job_text(job_text, JOB_TEXT_MAX_CHARS)
    num_predict, strip_markdown, forced_language = _cv_generation_options(prompt_name)
    language = forced_language or resolve_language(job_text, response_language)

    analysis_context = json.dumps(job_analysis or {}, ensure_ascii=False, indent=2)
    retrieval_query = f"{trimmed_job}\n{analysis_context}"
    candidate_context = candidate_context_for_query(retrieval_query, max_chars=12000)

    user_prompt = f"""
{language_instruction(language)}

Confirmed candidate facts retrieved from memory for this vacancy:
{candidate_context}

Structured vacancy analysis from memory:
{analysis_context}

Target company: {company or "Unknown"}
Target role: {role or "Unknown"}
Platform: {platform or "generic"}

Job description:
{trimmed_job}

{_cv_user_instructions(prompt_name)}
Use the saved analysis to prioritize confirmed matching requirements and ATS keywords.
Do not present missing or weak requirements as candidate skills.
Every factual claim must be supported by the confirmed candidate facts above.
"""
    raw = ask_llm(
        system_prompt,
        user_prompt,
        timeout=240,
        model=MODEL_CV,
        num_predict=num_predict,
        temperature=0.2,
        task=f"generate_cv:{platform or 'generic'}",
    )
    cleaned = _strip_markdown(raw) if strip_markdown else raw.strip()
    return cleaned

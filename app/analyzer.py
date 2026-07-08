import re

from app.config import JOB_TEXT_MAX_CHARS, MODEL_FAST
from app.language import language_instruction, resolve_language
from app.llm import ask_llm
from app.profile import (
    load_candidate_profile,
    load_interview_stories,
    load_missing_data,
    load_prompt,
    load_resume,
    trim_job_text,
)

def _extract_fit_score(analysis: str) -> int | None:
    match = re.search(r"fit score[^\d]*(\d{1,3})", analysis, re.IGNORECASE)
    if not match:
        return None
    score = int(match.group(1))
    return min(max(score, 0), 100)


def _extract_should_apply(analysis: str) -> str | None:
    match = re.search(
        r"##\s*should apply\?\s*\n+\s*(yes|maybe|no)\b",
        analysis,
        re.IGNORECASE,
    )
    return match.group(1).lower() if match else None


def _job_requires_developer_or_lead(job_text: str) -> bool:
    patterns = [
        r"опыт\s+работы\s+разработчик",
        r"(\d+)[\s-]*(?:лет|years?).{0,40}(?:разработчик|developer)",
        r"(?:разработчик|developer).{0,40}(\d+)[\s-]*(?:лет|years?)",
        r"тимлид|team\s*lead",
        r"руководств\w*\s+команд|people\s+management|engineering\s+manager",
        r"не\s+менее\s+\d+\s+человек",
    ]
    text = job_text.lower()
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _analysis_notes_role_gaps(analysis: str) -> bool:
    patterns = [
        r"(?:не\s+имеет|does\s+not\s+have|lacks|no\s+direct|нет\s+опыта|отсутствует)"
        r".{0,120}(?:разработчик|developer|тимлид|team\s*lead|symfony|php)",
        r"(?:разработчик|developer|тимлид|team\s*lead).{0,80}(?:не\s+имеет|does\s+not|lacks|нет)",
    ]
    return any(re.search(pattern, analysis, re.IGNORECASE | re.DOTALL) for pattern in patterns)


def _reconcile_fit_score(
    fit_score: int | None,
    should_apply: str | None,
    job_text: str,
    analysis: str,
) -> tuple[int | None, str | None]:
    if fit_score is None:
        return None, should_apply

    score = fit_score
    recommendation = should_apply

    if _job_requires_developer_or_lead(job_text) and _analysis_notes_role_gaps(analysis):
        score = min(score, 35)
        if recommendation == "yes":
            recommendation = "no"

    if recommendation == "no":
        score = min(score, 45)
    elif recommendation == "maybe":
        score = min(score, 65)

    if score >= 70 and recommendation == "no":
        score = min(score, 45)

    return score, recommendation


def _patch_analysis_scores(
    analysis: str,
    fit_score: int | None,
    should_apply: str | None,
) -> str:
    patched = analysis
    if fit_score is not None:
        patched = re.sub(
            r"(##\s*Fit Score\s*\n+\s*)\d{1,3}",
            rf"\g<1>{fit_score}",
            patched,
            count=1,
            flags=re.IGNORECASE,
        )
    if should_apply is not None:
        patched = re.sub(
            r"(##\s*Should Apply\?\s*\n+\s*)(yes|maybe|no)\b",
            rf"\g<1>{should_apply}",
            patched,
            count=1,
            flags=re.IGNORECASE,
        )
    return patched


def _extract_pitch(analysis: str) -> str | None:
    match = re.search(
        r"##\s*short pitch\s*\n+(.*?)(?=\n##|\Z)",
        analysis,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    return match.group(1).strip()


def extract_candidate_questions(analysis: str) -> list[str]:
    match = re.search(
        r"##\s*(?:Questions for the Candidate|Вопросы для кандидата)\s*\n+(.*?)(?=\n##|\Z)",
        analysis,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return []

    questions: list[str] = []
    for line in match.group(1).splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        cleaned = re.sub(r"^[-*•]\s*", "", cleaned)
        cleaned = re.sub(r"^\d+[.)]\s*", "", cleaned)
        if cleaned:
            questions.append(cleaned)
    return questions


def analyze_job(
    job_text: str,
    candidate_profile: dict | None = None,
    response_language: str = "auto",
) -> dict:
    profile = candidate_profile or load_candidate_profile()
    resume = load_resume()
    interview_stories = load_interview_stories()
    missing_data = load_missing_data()
    language = resolve_language(job_text, response_language)
    system_prompt = load_prompt("analyze_job")
    trimmed_job = trim_job_text(job_text, JOB_TEXT_MAX_CHARS)

    user_prompt = f"""
{language_instruction(language)}

Candidate profile:
{profile}

Resume:
{resume}

Interview stories:
{interview_stories}

Facts that require confirmation before use:
{missing_data}

Job description:
{trimmed_job}
"""
    result = ask_llm(
        system_prompt,
        user_prompt,
        model=MODEL_FAST,
        num_predict=1500,
    )
    fit_score = _extract_fit_score(result)
    should_apply = _extract_should_apply(result)
    fit_score, should_apply = _reconcile_fit_score(
        fit_score,
        should_apply,
        trimmed_job,
        result,
    )
    result = _patch_analysis_scores(result, fit_score, should_apply)
    return {
        "result": result,
        "fit_score": fit_score,
        "should_apply": should_apply,
        "pitch": _extract_pitch(result),
        "candidate_questions": extract_candidate_questions(result),
    }


def generate_cover_letter(
    job_text: str,
    company: str | None = None,
    role: str | None = None,
    response_language: str = "auto",
) -> str:
    profile = load_candidate_profile()
    resume = load_resume()
    interview_stories = load_interview_stories()
    missing_data = load_missing_data()
    language = resolve_language(job_text, response_language)
    system_prompt = load_prompt("cover_letter")
    trimmed_job = trim_job_text(job_text, JOB_TEXT_MAX_CHARS)

    user_prompt = f"""
{language_instruction(language)}

Candidate profile:
{profile}

Resume:
{resume}

Interview stories:
{interview_stories}

Facts that require confirmation before use:
{missing_data}

Company: {company or "Unknown"}
Role: {role or "Unknown"}

Job description:
{trimmed_job}
"""
    return ask_llm(
        system_prompt,
        user_prompt,
        model=MODEL_FAST,
        num_predict=1200,
    )

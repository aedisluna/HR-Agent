import re

from pydantic import ValidationError

from app.analysis_models import JobAnalysis, analysis_payload, render_job_analysis
from app.config import JOB_TEXT_MAX_CHARS, MODEL_FAST
from app.language import language_instruction, resolve_language
from app.llm import LLMError, ask_llm
from app.memory import candidate_context_for_analysis
from app.profile import (
    format_for_prompt,
    load_candidate_profile,
    load_interview_stories,
    load_missing_data,
    load_prompt,
    load_resume,
    trim_job_text,
)

def _extract_fit_score(analysis: str) -> int | None:
    patterns = (
        r"fit score[^\d]*(\d{1,3})",
        r"##\s*fit score\s*\n+\s*(\d{1,3})",
        r"(\d{1,3})\s*/\s*100",
    )
    for pattern in patterns:
        match = re.search(pattern, analysis, re.IGNORECASE)
        if match:
            score = int(match.group(1))
            return min(max(score, 0), 100)
    return None


def _extract_should_apply(analysis: str) -> str | None:
    match = re.search(
        r"##\s*should apply\?\s*\n+\s*(yes|maybe|no)\b",
        analysis,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).lower()

    fallback = re.search(
        r"(?:should apply|стоит откликаться)[^\n]*\b(yes|maybe|no)\b",
        analysis,
        re.IGNORECASE,
    )
    return fallback.group(1).lower() if fallback else None


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


def _validate_assessment_evidence(
    analysis: JobAnalysis,
    candidate_context: str,
) -> JobAnalysis:
    available_keys = {
        line.partition(":")[0].strip()
        for line in candidate_context.splitlines()
        if ":" in line
    }
    invalid: list[str] = []
    for assessment in analysis.requirement_assessments:
        if assessment.status != "matched":
            continue
        for evidence_key in assessment.evidence:
            if evidence_key not in available_keys:
                invalid.append(evidence_key)
    if invalid:
        raise ValueError(
            "matched assessments reference unavailable candidate fact keys: "
            + ", ".join(sorted(set(invalid)))
        )
    return analysis


def _request_structured_analysis(
    system_prompt: str,
    user_prompt: str,
    candidate_context: str,
) -> JobAnalysis:
    raw = ask_llm(
        system_prompt,
        user_prompt,
        model=MODEL_FAST,
        num_predict=1800,
        response_schema=JobAnalysis,
        temperature=0,
        task="analyze_job",
    )
    try:
        structured = JobAnalysis.model_validate_json(raw)
        return _validate_assessment_evidence(structured, candidate_context)
    except (ValidationError, ValueError) as first_exc:
        repair_prompt = f"""{user_prompt}

The previous response failed validation:
{first_exc}

Regenerate the complete JSON object. Assess every must-have requirement using the
exact same requirement text. A matched item must cite one or more exact candidate
fact keys that appear before a colon in the confirmed context. Keep fit_score and
should_apply consistent.
"""
        repaired = ask_llm(
            system_prompt,
            repair_prompt,
            model=MODEL_FAST,
            num_predict=1800,
            response_schema=JobAnalysis,
            temperature=0,
            task="analyze_job_retry",
        )
        try:
            structured = JobAnalysis.model_validate_json(repaired)
            return _validate_assessment_evidence(structured, candidate_context)
        except (ValidationError, ValueError) as exc:
            raise LLMError(
                f"Ollama returned invalid structured job analysis after retry: {exc}"
            ) from exc


def analyze_job(
    job_text: str,
    candidate_profile: dict | None = None,
    response_language: str = "auto",
) -> dict:
    trimmed_job = trim_job_text(job_text, JOB_TEXT_MAX_CHARS)
    if candidate_profile is not None:
        candidate_context = format_for_prompt(candidate_profile)
    else:
        candidate_context = candidate_context_for_analysis(trimmed_job, max_chars=16000)

    missing_context = format_for_prompt(load_missing_data())[:4000]
    language = resolve_language(job_text, response_language)
    system_prompt = load_prompt("analyze_job")
    user_prompt = f"""
{language_instruction(language)}

Confirmed candidate facts retrieved for this vacancy:
{candidate_context}

Facts that require confirmation before use:
{missing_context}

Job description:
{trimmed_job}

Return only data matching the supplied JSON schema. Keep requirements atomic and
put important exact ATS terms into keywords. Never mark an unconfirmed fact as a match.
"""
    structured = _request_structured_analysis(
        system_prompt,
        user_prompt,
        candidate_context,
    )

    provisional_text = render_job_analysis(structured)
    fit_score, should_apply = _reconcile_fit_score(
        structured.fit_score,
        structured.should_apply,
        trimmed_job,
        provisional_text,
    )
    if fit_score is not None:
        structured.fit_score = fit_score
    if should_apply is not None:
        structured.should_apply = should_apply

    result = render_job_analysis(structured)
    return {
        "result": result,
        "structured": analysis_payload(structured),
        "fit_score": structured.fit_score,
        "should_apply": structured.should_apply,
        "pitch": structured.short_pitch,
        "candidate_questions": structured.questions_for_candidate,
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
{format_for_prompt(profile)}

Resume:
{resume}

Interview stories:
{format_for_prompt(interview_stories)}

Facts that require confirmation before use:
{format_for_prompt(missing_data)}

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
        temperature=0.2,
        task="generate_cover_letter",
    )

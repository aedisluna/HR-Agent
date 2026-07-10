from app.config import JOB_TEXT_MAX_CHARS, MODEL_FAST
from app.language import language_instruction, resolve_language
from app.llm import ask_llm
from app.profile import (
    format_for_prompt,
    load_candidate_profile,
    load_interview_stories,
    load_missing_data,
    load_prompt,
    load_resume,
    load_standard_answers,
    trim_job_text,
)

def generate_answers(
    job_text: str,
    questions: list[str],
    profile: dict | None = None,
    standard_answers: dict | None = None,
    response_language: str = "auto",
) -> str:
    profile = profile or load_candidate_profile()
    standard_answers = standard_answers or load_standard_answers()
    resume = load_resume()
    interview_stories = load_interview_stories()
    missing_data = load_missing_data()
    language = resolve_language(job_text, response_language)
    system_prompt = load_prompt("generate_answers")

    questions_block = "\n".join(f"- {question}" for question in questions)
    trimmed_job = trim_job_text(job_text, JOB_TEXT_MAX_CHARS)
    user_prompt = f"""
{language_instruction(language)}

Candidate profile:
{format_for_prompt(profile)}

Resume:
{resume}

Known standard answers:
{format_for_prompt(standard_answers)}

Interview stories (use for behavioral questions):
{format_for_prompt(interview_stories)}

Facts that require confirmation before use:
{format_for_prompt(missing_data)}

Job description:
{trimmed_job}

Questions from application form:
{questions_block}
"""
    return ask_llm(
        system_prompt,
        user_prompt,
        model=MODEL_FAST,
        num_predict=1800,
        temperature=0.2,
        task="generate_answers",
    )

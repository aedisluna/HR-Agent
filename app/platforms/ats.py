"""Generic ATS form field matching using learned answers and LLM."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.answer_generator import generate_answers
from app.cv_generator import generate_tailored_cv
from app.memory import (
    analysis_dict,
    find_application,
    job_text_hash,
    latest_job_analysis,
)
from app.profile import load_candidate_profile
from app.storage import LearnedAnswer


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _match_learned(label: str, learned: list[LearnedAnswer]) -> dict[str, Any] | None:
    normalized_label = _normalize(label)
    best: dict[str, Any] | None = None
    best_score = 0

    for item in learned:
        pattern = _normalize(item.question_pattern)
        if not pattern:
            continue

        score = 0
        if pattern in normalized_label:
            score = len(pattern)
        elif normalized_label in pattern:
            score = len(normalized_label)
        else:
            pattern_tokens = set(pattern.split())
            label_tokens = set(normalized_label.split())
            overlap = pattern_tokens & label_tokens
            if len(overlap) >= 2:
                score = len(overlap)
            elif len(overlap) == 1:
                token = next(iter(overlap))
                if len(token) >= 5:
                    score = 2

        if score > best_score:
            best_score = score
            best = {
                "answer": item.answer,
                "confidence": item.confidence,
                "needs_confirmation": item.requires_confirmation,
                "source": "learned_answers",
            }

    return best if best_score >= 2 else None


def _split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.split(None, 1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _match_identity(label: str, profile: dict[str, Any]) -> dict[str, Any] | None:
    identity = profile.get("identity") or {}
    preferred = str(identity.get("preferred_name") or "").strip()
    legal = str(identity.get("legal_name") or "").strip()
    location = str(identity.get("current_location") or "").strip()
    email = str(identity.get("email") or "").strip()
    phone = str(identity.get("phone") or "").strip()
    telegram = str(identity.get("telegram") or "").strip()
    linkedin_url = str(identity.get("linkedin_url") or "").strip()

    preferred_first, preferred_last = _split_name(preferred)
    legal_first, legal_last = _split_name(legal)
    normalized = _normalize(label)

    rules: list[tuple[tuple[str, ...], str, bool]] = [
        (
            ("email address", "e-mail", "email", "почта"),
            email,
            False,
        ),
        (
            ("phone number", "mobile phone", "mobile", "phone", "телефон"),
            phone,
            False,
        ),
        (
            ("telegram username", "telegram handle", "telegram"),
            telegram,
            False,
        ),
        (
            ("linkedin profile", "linkedin url", "linkedin"),
            linkedin_url,
            False,
        ),
        (
            ("preferred first name", "preferred name"),
            preferred_first,
            False,
        ),
        (
            ("legal first name",),
            legal_first,
            False,
        ),
        (
            ("first name", "given name", "forename", "имя"),
            preferred_first or legal_first,
            False,
        ),
        (
            ("legal last name",),
            legal_last,
            False,
        ),
        (
            ("last name", "family name", "surname", "фамилия"),
            preferred_last or legal_last,
            False,
        ),
        (
            ("full name",),
            preferred or legal,
            False,
        ),
        (
            (
                "current location",
                "your location",
                "where are you located",
                "city and state",
                "city",
            ),
            location,
            False,
        ),
    ]

    for patterns, answer, needs_confirmation in rules:
        if not answer:
            continue
        for pattern in patterns:
            if pattern in normalized or normalized == pattern:
                return {
                    "answer": answer,
                    "confidence": "high",
                    "needs_confirmation": needs_confirmation,
                    "source": "profile",
                }

    return None


def _parse_llm_field_answers(
    llm_text: str,
    questions: list[str],
) -> dict[str, dict[str, Any]]:
    parsed: dict[str, dict[str, Any]] = {}
    blocks = re.split(r"(?=^### )", llm_text, flags=re.MULTILINE)
    ordered_answers: list[dict[str, Any]] = []

    for block in blocks:
        header = re.match(r"^###\s*(.+?)\s*$", block, flags=re.MULTILINE)
        if not header:
            continue

        question = header.group(1).strip()
        answer_match = re.search(r"\*\*Answer:\*\*\s*(.+)", block)
        confidence_match = re.search(
            r"\*\*Confidence:\*\*\s*(high|medium|low)", block, re.IGNORECASE
        )
        confirm_match = re.search(
            r"\*\*Needs confirmation:\*\*\s*(yes|no)", block, re.IGNORECASE
        )

        if not answer_match:
            continue

        answer = answer_match.group(1).strip()
        if answer.upper() == "QUESTION_NEEDED":
            continue

        item = {
            "answer": answer,
            "confidence": (confidence_match.group(1).lower() if confidence_match else "medium"),
            "needs_confirmation": (
                confirm_match.group(1).lower() == "yes" if confirm_match else True
            ),
            "source": "llm",
        }
        parsed[question] = item
        ordered_answers.append(item)

    if not parsed and ordered_answers:
        for question, item in zip(questions, ordered_answers):
            parsed[question] = item

    return parsed


def _should_fill(confidence: str, needs_confirmation: bool, platform: str) -> bool:
    if confidence == "low":
        return False
    if platform in {"hh", "external_ats"} or platform.startswith("ats:"):
        return True
    return confidence == "high" and not needs_confirmation


def _is_cover_letter_field(label: str) -> bool:
    normalized = _normalize(label)
    if not normalized:
        return False
    patterns = (
        "сопроводительное",
        "сопроводительное письмо",
        "cover letter",
        "covering letter",
        "motivation letter",
        "accompanying letter",
    )
    return any(pattern in normalized for pattern in patterns)


def map_form_fields(
    *,
    job_text: str,
    fields: list[dict[str, Any]],
    db: Session,
    use_llm: bool = True,
    response_language: str = "auto",
    platform: str = "generic",
    company: str | None = None,
    role: str | None = None,
    url: str | None = None,
) -> list[dict[str, Any]]:
    learned = db.query(LearnedAnswer).all()
    profile = load_candidate_profile()
    questions = [field.get("label") or field.get("name") or field.get("id") or "Field" for field in fields]
    llm_answers: dict[str, dict[str, Any]] = {}

    unresolved = []
    for field, question in zip(fields, questions):
        if _is_cover_letter_field(question):
            continue
        if _match_identity(question, profile):
            continue
        if not _match_learned(question, learned):
            unresolved.append(question)

    if use_llm and unresolved:
        llm_text = generate_answers(
            job_text=job_text,
            questions=unresolved,
            response_language=response_language,
        )
        llm_answers = _parse_llm_field_answers(llm_text, unresolved)

    cover_letter_text: str | None = None
    if use_llm and any(_is_cover_letter_field(q) for q in questions):
        application = find_application(db, url=url)
        analysis_record = latest_job_analysis(
            db,
            application_id=application.id if application else None,
            url=url,
            job_text=job_text,
        )
        saved_analysis = analysis_dict(analysis_record)
        if (
            saved_analysis is None
            and application
            and application.analysis_result
            and application.raw_job_text
            and job_text_hash(application.raw_job_text) == job_text_hash(job_text)
        ):
            saved_analysis = {"legacy_analysis": application.analysis_result}
        cover_letter_text = generate_tailored_cv(
            job_text=job_text,
            company=company,
            role=role,
            response_language=response_language,
            platform=platform,
            job_analysis=saved_analysis,
        )

    results = []
    for field, question in zip(fields, questions):
        if _is_cover_letter_field(question):
            if not use_llm:
                results.append(
                    {
                        "field_id": field.get("id"),
                        "label": question,
                        "answer": None,
                        "confidence": "low",
                        "needs_confirmation": True,
                        "source": "none",
                        "fill": False,
                    }
                )
                continue

            results.append(
                {
                    "field_id": field.get("id"),
                    "label": question,
                    "answer": cover_letter_text,
                    "confidence": "high",
                    "needs_confirmation": True,
                    "source": "tailored_cv",
                    "fill": _should_fill("high", True, platform),
                }
            )
            continue

        matched = _match_identity(question, profile)
        if not matched:
            matched = _match_learned(question, learned)
        if not matched:
            matched = llm_answers.get(question)

        if not matched:
            results.append(
                {
                    "field_id": field.get("id"),
                    "label": question,
                    "answer": None,
                    "confidence": "low",
                    "needs_confirmation": True,
                    "source": "none",
                    "fill": False,
                }
            )
            continue

        confidence = matched["confidence"]
        needs_confirmation = matched["needs_confirmation"]
        results.append(
            {
                "field_id": field.get("id"),
                "label": question,
                "answer": matched["answer"],
                "confidence": confidence,
                "needs_confirmation": needs_confirmation,
                "source": matched["source"],
                "fill": _should_fill(confidence, needs_confirmation, platform),
            }
        )

    return results

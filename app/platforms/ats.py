"""Generic ATS form field matching using learned answers and LLM."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.answer_generator import generate_answers
from app.cv_generator import generate_tailored_cv
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
) -> list[dict[str, Any]]:
    learned = db.query(LearnedAnswer).all()
    questions = [field.get("label") or field.get("name") or field.get("id") or "Field" for field in fields]
    llm_answers: dict[str, dict[str, Any]] = {}

    unresolved = []
    for field, question in zip(fields, questions):
        if _is_cover_letter_field(question):
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

            cv_text = generate_tailored_cv(
                job_text=job_text,
                company=company,
                role=role,
                response_language=response_language,
                platform=platform,
            )
            results.append(
                {
                    "field_id": field.get("id"),
                    "label": question,
                    "answer": cv_text,
                    "confidence": "high",
                    "needs_confirmation": True,
                    "source": "tailored_cv",
                    "fill": _should_fill("high", True, platform),
                }
            )
            continue

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

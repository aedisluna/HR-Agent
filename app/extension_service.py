"""Helpers for extension question flows."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.analyzer import extract_candidate_questions
from app.profile import load_missing_data
from app.storage import Application, LearnedAnswer, utc_now_iso


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def upsert_learned_answer(
    db: Session,
    *,
    question_pattern: str,
    answer: str,
    confidence: str = "high",
    requires_confirmation: bool = False,
) -> LearnedAnswer:
    normalized = _normalize(question_pattern)
    existing = db.query(LearnedAnswer).all()
    matched = None

    for item in existing:
        if _normalize(item.question_pattern) == normalized:
            matched = item
            break

    if matched:
        matched.answer = answer
        matched.confidence = confidence
        matched.requires_confirmation = requires_confirmation
        db.commit()
        db.refresh(matched)
        return matched

    learned = LearnedAnswer(
        question_pattern=question_pattern,
        answer=answer,
        confidence=confidence,
        requires_confirmation=requires_confirmation,
    )
    db.add(learned)
    db.commit()
    db.refresh(learned)
    return learned


def _question_is_answered(question: str, learned: list[LearnedAnswer]) -> bool:
    normalized_question = _normalize(question)
    for item in learned:
        pattern = _normalize(item.question_pattern)
        if not pattern:
            continue
        if pattern in normalized_question or normalized_question in pattern:
            return True
        pattern_tokens = set(pattern.split())
        question_tokens = set(normalized_question.split())
        if len(pattern_tokens & question_tokens) >= 2:
            return True
    return False


def get_missing_profile_questions(db: Session) -> list[dict[str, Any]]:
    missing_data = load_missing_data()
    learned = db.query(LearnedAnswer).all()
    pending: list[dict[str, Any]] = []

    for section_name, section in missing_data.items():
        if not isinstance(section, dict):
            continue
        for key, item in section.items():
            if not isinstance(item, dict):
                continue
            question = item.get("question")
            if not question:
                continue

            if _question_is_answered(question, learned):
                continue

            pending.append(
                {
                    "id": f"{section_name}.{key}",
                    "question": question,
                    "importance": item.get("importance", "medium"),
                    "current_assumption": item.get("current_assumption")
                    or item.get("risk")
                    or "",
                    "source": "missing_data",
                }
            )

    return pending


def get_analysis_questions(analysis_text: str, db: Session) -> list[dict[str, Any]]:
    learned = db.query(LearnedAnswer).all()
    pending: list[dict[str, Any]] = []

    for index, question in enumerate(extract_candidate_questions(analysis_text)):
        if _question_is_answered(question, learned):
            continue
        pending.append(
            {
                "id": f"analysis.{index}",
                "question": question,
                "importance": "high",
                "current_assumption": "",
                "source": "analysis",
            }
        )

    return pending


def mappings_need_user_input(mappings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pending = []
    for item in mappings:
        if item.get("answer") and item.get("fill"):
            continue
        pending.append(
            {
                "id": item.get("field_id") or item.get("label"),
                "question": item.get("label") or "Unknown question",
                "suggested_answer": item.get("answer") or "",
                "importance": "high" if not item.get("answer") else "medium",
                "current_assumption": item.get("answer") or "",
                "source": "form_mapping",
                "field_id": item.get("field_id"),
            }
        )
    return pending


def track_application(
    db: Session,
    *,
    platform: str,
    url: str,
    company: str | None = None,
    role: str | None = None,
    status: str = "draft",
    job_text: str | None = None,
    fit_score: int | None = None,
    notes: str | None = None,
    generated_pitch: str | None = None,
    generated_cover_letter: str | None = None,
    analysis_result: str | None = None,
) -> Application:
    existing = (
        db.query(Application)
        .filter(Application.url == url)
        .order_by(Application.id.desc())
        .first()
    )

    resolved_company = (company or "Unknown").strip() or "Unknown"
    resolved_role = (role or "Unknown").strip() or "Unknown"

    if existing:
        existing.company = resolved_company
        existing.role = resolved_role
        existing.source = platform
        if job_text:
            existing.raw_job_text = job_text[:12000]
        if fit_score is not None:
            existing.fit_score = fit_score
        if notes is not None:
            existing.notes = notes
        if generated_pitch:
            existing.generated_pitch = generated_pitch
        if generated_cover_letter:
            existing.generated_cover_letter = generated_cover_letter
        if analysis_result:
            existing.analysis_result = analysis_result
        existing.status = status
        if status == "applied" and not existing.applied_at:
            existing.applied_at = utc_now_iso()
        db.commit()
        db.refresh(existing)
        return existing

    application = Application(
        company=resolved_company,
        role=resolved_role,
        source=platform,
        url=url,
        status=status,
        fit_score=fit_score,
        applied_at=utc_now_iso() if status == "applied" else None,
        notes=notes,
        raw_job_text=job_text[:12000] if job_text else None,
        generated_pitch=generated_pitch,
        generated_cover_letter=generated_cover_letter,
        analysis_result=analysis_result,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application

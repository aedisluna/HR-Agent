"""Import profile pack data into SQLite learned_answers."""

from __future__ import annotations

from typing import Any

from app.storage import LearnedAnswer, SessionLocal, init_db


def _flatten_standard_answers(
    data: dict[str, Any],
    prefix: str = "",
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if not isinstance(value, dict):
            continue

        if "answer" in value:
            patterns = value.get("question_patterns") or []
            path_pattern = path.replace("_", " ").replace(".", " / ")
            pattern_rows = patterns or [path_pattern]
            for pattern in pattern_rows:
                items.append(
                    {
                        "question_pattern": str(pattern).strip(),
                        "answer": str(value["answer"]).strip(),
                        "confidence": value.get("confidence", "medium"),
                        "requires_confirmation": bool(
                            value.get("requires_confirmation", True)
                        ),
                    }
                )
            continue

        items.extend(_flatten_standard_answers(value, path))

    return items


def _flatten_interview_stories(data: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    stories = data.get("stories", {})

    for story_key, story in stories.items():
        if not isinstance(story, dict):
            continue

        patterns = story.get("question_patterns", [])
        answer_en = story.get("answer_en", "").strip()
        if not patterns or not answer_en:
            continue

        for pattern in patterns:
            items.append(
                {
                    "question_pattern": pattern,
                    "answer": answer_en,
                    "confidence": "high",
                    "requires_confirmation": False,
                }
            )

    return items


def seed_learned_answers(
    standard_answers: dict[str, Any],
    interview_stories: dict[str, Any] | None = None,
    replace_existing: bool = True,
) -> int:
    init_db()
    db = SessionLocal()

    try:
        if replace_existing:
            db.query(LearnedAnswer).delete()

        rows = _flatten_standard_answers(standard_answers)
        if interview_stories:
            rows.extend(_flatten_interview_stories(interview_stories))

        for row in rows:
            db.add(LearnedAnswer(**row))

        db.commit()
        return len(rows)
    finally:
        db.close()


def seed_from_data_files(replace_existing: bool = True) -> int:
    from app.profile import load_interview_stories, load_standard_answers

    return seed_learned_answers(
        standard_answers=load_standard_answers(),
        interview_stories=load_interview_stories(),
        replace_existing=replace_existing,
    )

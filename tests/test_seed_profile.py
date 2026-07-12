import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import seed_profile
from app.storage import Base, LearnedAnswer


@pytest.fixture
def seeded_db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(seed_profile, "init_db", lambda: None)
    monkeypatch.setattr(seed_profile, "SessionLocal", test_session)
    try:
        yield test_session
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_flatteners_keep_question_contracts_and_skip_invalid_rows():
    standard_answers = {
        "availability": {
            "answer": "Two weeks.",
            "question_patterns": ["Notice period", "Availability"],
            "confidence": "high",
            "requires_confirmation": False,
        },
        "nested": {"visa": {"answer": "No sponsorship required."}},
        "metadata": "ignored",
    }
    stories = {
        "stories": {
            "migration": {
                "question_patterns": ["Tell me about a migration"],
                "answer_en": "I validated migration flows.",
            },
            "broken": {"question_patterns": ["Ignored"], "answer_en": ""},
        }
    }

    flattened_answers = seed_profile._flatten_standard_answers(standard_answers)
    flattened_stories = seed_profile._flatten_interview_stories(stories)

    assert flattened_answers == [
        {
            "question_pattern": "Notice period",
            "answer": "Two weeks.",
            "confidence": "high",
            "requires_confirmation": False,
        },
        {
            "question_pattern": "Availability",
            "answer": "Two weeks.",
            "confidence": "high",
            "requires_confirmation": False,
        },
        {
            "question_pattern": "nested / visa",
            "answer": "No sponsorship required.",
            "confidence": "medium",
            "requires_confirmation": True,
        },
    ]
    assert flattened_stories == [
        {
            "question_pattern": "Tell me about a migration",
            "answer": "I validated migration flows.",
            "confidence": "high",
            "requires_confirmation": False,
        }
    ]


def test_seed_preserves_existing_answers_when_replace_is_disabled(seeded_db):
    standard_answers = {
        "availability": {
            "answer": "Two weeks.",
            "question_patterns": ["Notice period"],
            "confidence": "high",
            "requires_confirmation": False,
        }
    }
    stories = {
        "stories": {
            "migration": {
                "question_patterns": ["Tell me about a migration"],
                "answer_en": "I validated migration flows.",
            }
        }
    }

    assert seed_profile.seed_learned_answers(standard_answers, stories) == 2

    db = seeded_db()
    try:
        db.add(
            LearnedAnswer(
                question_pattern="Custom answer",
                answer="Keep me.",
                confidence="high",
                requires_confirmation=False,
            )
        )
        db.commit()
    finally:
        db.close()

    assert seed_profile.seed_learned_answers(
        standard_answers,
        stories,
        replace_existing=False,
    ) == 0

    db = seeded_db()
    try:
        assert [item.question_pattern for item in db.query(LearnedAnswer).order_by(LearnedAnswer.id).all()] == [
            "Notice period",
            "Tell me about a migration",
            "Custom answer",
        ]
    finally:
        db.close()
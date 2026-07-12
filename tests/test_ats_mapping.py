from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.platforms.ats import map_form_fields
from app.storage import Base, LearnedAnswer


PROFILE = {
    "identity": {
        "preferred_name": "Alex Doe",
        "legal_name": "Alexander Doe",
        "current_location": "Example City, Country",
        "email": "alex@example.test",
        "phone": "+10000000000",
        "telegram": "@alex_doe",
        "linkedin_url": "https://www.linkedin.com/in/alex-doe/",
    }
}
JOB_TEXT = "QA Engineer role requiring API testing and Postman experience."


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_profile_identity_is_auto_filled_but_unknown_field_is_not(db):
    fields = [
        {"id": "email", "label": "Email", "field_type": "email"},
        {"id": "name", "label": "First name"},
        {"id": "salary", "label": "Salary expectations"},
    ]
    with patch("app.platforms.ats.load_candidate_profile", return_value=PROFILE):
        result = map_form_fields(
            job_text=JOB_TEXT,
            fields=fields,
            db=db,
            use_llm=False,
            platform="linkedin",
        )

    assert result == [
        {
            "field_id": "email",
            "label": "Email",
            "answer": "alex@example.test",
            "confidence": "high",
            "needs_confirmation": False,
            "source": "profile",
            "fill": True,
        },
        {
            "field_id": "name",
            "label": "First name",
            "answer": "Alex",
            "confidence": "high",
            "needs_confirmation": False,
            "source": "profile",
            "fill": True,
        },
        {
            "field_id": "salary",
            "label": "Salary expectations",
            "answer": None,
            "confidence": "low",
            "needs_confirmation": True,
            "source": "none",
            "fill": False,
        },
    ]


def test_learned_answer_respects_confirmation_on_linkedin(db):
    db.add(
        LearnedAnswer(
            question_pattern="visa sponsorship",
            answer="No sponsorship required.",
            confidence="medium",
            requires_confirmation=True,
        )
    )
    db.commit()

    with patch("app.platforms.ats.load_candidate_profile", return_value={}):
        result = map_form_fields(
            job_text=JOB_TEXT,
            fields=[{"id": "visa", "label": "Do you need visa sponsorship?"}],
            db=db,
            use_llm=False,
            platform="linkedin",
        )

    assert result[0]["answer"] == "No sponsorship required."
    assert result[0]["source"] == "learned_answers"
    assert result[0]["needs_confirmation"] is True
    assert result[0]["fill"] is False


def test_unresolved_questions_are_sent_to_llm_and_safe_answer_is_filled(db):
    llm_response = """### Desired salary
**Answer:** 100000 RUB gross
**Confidence:** high
**Needs confirmation:** no
"""
    fields = [
        {"id": "email", "label": "Email"},
        {"id": "salary", "label": "Desired salary"},
    ]
    with patch("app.platforms.ats.load_candidate_profile", return_value=PROFILE), patch(
        "app.platforms.ats.generate_answers", return_value=llm_response
    ) as generate_answers:
        result = map_form_fields(
            job_text=JOB_TEXT,
            fields=fields,
            db=db,
            use_llm=True,
            response_language="en",
            platform="linkedin",
        )

    assert generate_answers.call_args.kwargs == {
        "job_text": JOB_TEXT,
        "questions": ["Desired salary"],
        "response_language": "en",
    }
    assert result[0]["source"] == "profile"
    assert result[1] == {
        "field_id": "salary",
        "label": "Desired salary",
        "answer": "100000 RUB gross",
        "confidence": "high",
        "needs_confirmation": False,
        "source": "llm",
        "fill": True,
    }


def test_question_needed_and_low_confidence_never_auto_fill(db):
    llm_response = """### Salary
**Answer:** QUESTION_NEEDED
**Confidence:** high
**Needs confirmation:** no

### Start date
**Answer:** Immediately
**Confidence:** low
**Needs confirmation:** no
"""
    with patch("app.platforms.ats.load_candidate_profile", return_value={}), patch(
        "app.platforms.ats.generate_answers", return_value=llm_response
    ):
        result = map_form_fields(
            job_text=JOB_TEXT,
            fields=[
                {"id": "salary", "label": "Salary"},
                {"id": "start", "label": "Start date"},
            ],
            db=db,
            use_llm=True,
            platform="external_ats",
        )

    assert result[0]["source"] == "none"
    assert result[0]["fill"] is False
    assert result[1]["confidence"] == "low"
    assert result[1]["fill"] is False


def test_cover_letter_needs_llm_and_is_not_filled_on_generic_platform(db):
    fields = [{"id": "letter", "label": "Cover letter", "field_type": "textarea"}]
    with patch("app.platforms.ats.load_candidate_profile", return_value={}), patch(
        "app.platforms.ats.generate_tailored_cv", return_value="Tailored letter"
    ) as generate_cv:
        result = map_form_fields(
            job_text=JOB_TEXT,
            fields=fields,
            db=db,
            use_llm=True,
            platform="generic",
            company="Example Co",
            role="QA Engineer",
        )

    assert generate_cv.call_count == 1
    assert result[0]["source"] == "tailored_cv"
    assert result[0]["answer"] == "Tailored letter"
    assert result[0]["needs_confirmation"] is True
    assert result[0]["fill"] is False


def test_cover_letter_is_left_empty_when_llm_is_disabled(db):
    with patch("app.platforms.ats.load_candidate_profile", return_value={}), patch(
        "app.platforms.ats.generate_tailored_cv"
    ) as generate_cv:
        result = map_form_fields(
            job_text=JOB_TEXT,
            fields=[{"id": "letter", "label": "Cover letter"}],
            db=db,
            use_llm=False,
            platform="external_ats",
        )

    generate_cv.assert_not_called()
    assert result[0]["answer"] is None
    assert result[0]["source"] == "none"
    assert result[0]["fill"] is False
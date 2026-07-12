import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as api
from app.config import APP_VERSION
from app.llm import LLMError
from app.profile import ProfileDataError
from app.storage import (
    Application,
    Base,
    GeneratedArtifact,
    JobAnalysisRecord,
    LLMRun,
    get_db,
)


JOB_TEXT = "QA Engineer role requiring API testing and Postman experience."
VACANCY_URL = "https://example.test/jobs/qa-engineer"


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    def override_get_db():
        db = test_session()
        try:
            yield db
        finally:
            db.close()

    api.app.dependency_overrides[get_db] = override_get_db
    api.app.state.test_session_factory = test_session
    test_client = TestClient(api.app)
    try:
        yield test_client
    finally:
        test_client.close()
        api.app.dependency_overrides.clear()
        del api.app.state.test_session_factory
        Base.metadata.drop_all(engine)
        engine.dispose()


def _application_payload(**overrides):
    payload = {
        "company": "Example Co",
        "role": "QA Engineer",
        "source": "manual",
        "url": VACANCY_URL,
        "status": "draft",
        "fit_score": 73,
    }
    payload.update(overrides)
    return payload


def _analysis():
    return {
        "fit_score": 82,
        "pitch": "Relevant QA experience.",
        "result": "Structured analysis result.",
        "structured": {"keywords": []},
    }


def _linkedin_cv():
    return (
        "PROFESSIONAL SUMMARY\nRelevant QA Engineer.\n"
        "TECHNICAL SKILLS\nAPI testing\n"
        "PROFESSIONAL EXPERIENCE\nValidated integrations.\n"
        "LANGUAGES\nEnglish"
    )


def test_health_and_validation_contract(client):
    health = client.get("/health")

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "version": APP_VERSION}

    invalid_request = client.post("/analyze-job", json={"job_text": "too short"})
    assert invalid_request.status_code == 422


def test_analyze_job_translates_llm_failure_to_service_unavailable(client):
    with patch("app.main.analyze_job", side_effect=LLMError("Ollama offline")):
        response = client.post("/analyze-job", json={"job_text": JOB_TEXT})

    assert response.status_code == 503
    assert response.json()["detail"] == "Ollama offline"


def test_application_crud_validates_status_and_applied_timestamp(client):
    created = client.post("/applications", json=_application_payload())

    assert created.status_code == 200
    application_id = created.json()["id"]
    assert created.json()["applied_at"] is None

    updated = client.patch(
        f"/applications/{application_id}",
        json={"status": "applied", "notes": "Applied through ATS"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "applied"
    assert updated.json()["applied_at"]
    assert updated.json()["notes"] == "Applied through ATS"

    invalid_status = client.post(
        "/applications", json=_application_payload(status="unknown")
    )
    assert invalid_status.status_code == 400
    assert invalid_status.json()["detail"] == "Invalid status"

    missing = client.patch("/applications/999", json={"status": "draft"})
    assert missing.status_code == 404

    deleted = client.delete(f"/applications/{application_id}")
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}
    assert client.get("/applications").json() == []


def test_extension_tracking_upserts_and_returns_application_by_url(client):
    created = client.post(
        "/extension/track-application",
        json={
            "platform": "external_ats",
            "url": VACANCY_URL,
            "company": "Example Co",
            "role": "QA Engineer",
            "job_text": JOB_TEXT,
            "status": "draft",
        },
    )
    assert created.status_code == 200
    application_id = created.json()["id"]

    updated = client.post(
        "/extension/track-application",
        json={
            "platform": "external_ats",
            "url": VACANCY_URL,
            "company": "Example Co",
            "role": "QA Engineer",
            "fit_score": 88,
            "status": "applied",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == application_id
    assert updated.json()["fit_score"] == 88
    assert updated.json()["applied_at"]

    by_url = client.get("/extension/application-by-url", params={"url": VACANCY_URL})
    assert by_url.status_code == 200
    assert by_url.json()["application"]["id"] == application_id

    applications = client.get("/extension/applications", params={"limit": 1})
    assert applications.status_code == 200
    assert [item["id"] for item in applications.json()] == [application_id]


def test_learned_answers_create_list_and_extension_upsert(client):
    created = client.post(
        "/learned-answers",
        json={
            "question_pattern": "Do you need visa sponsorship?",
            "answer": "No.",
            "confidence": "high",
            "requires_confirmation": False,
        },
    )
    assert created.status_code == 200

    first_save = client.post(
        "/extension/save-answer",
        json={
            "question_pattern": "What is your notice period?",
            "answer": "Two weeks.",
        },
    )
    second_save = client.post(
        "/extension/save-answer",
        json={
            "question_pattern": "  what is your notice period?  ",
            "answer": "One month.",
            "confidence": "medium",
            "requires_confirmation": True,
        },
    )

    assert first_save.status_code == 200
    assert second_save.status_code == 200
    assert second_save.json()["id"] == first_save.json()["id"]
    assert second_save.json()["answer"] == "One month."

    answers = client.get("/learned-answers")
    assert answers.status_code == 200
    assert len(answers.json()) == 2


def test_fill_form_returns_review_safe_mapping_contract(client):
    mappings = [
        {
            "field_id": "email",
            "label": "Email",
            "answer": "qa@example.test",
            "fill": True,
        },
        {
            "field_id": "salary",
            "label": "Salary expectations",
            "answer": "Need confirmation",
            "fill": False,
        },
        {"field_id": "portfolio", "label": "Portfolio", "answer": "", "fill": False},
    ]
    with patch("app.main.map_form_fields", return_value=mappings) as map_fields:
        response = client.post(
            "/extension/fill-form",
            json={
                "platform": "external_ats",
                "url": VACANCY_URL,
                "job_text": JOB_TEXT,
                "use_llm": False,
                "fields": [
                    {"id": "email", "label": "Email", "field_type": "email"},
                    {"id": "salary", "label": "Salary expectations"},
                    {"id": "portfolio", "label": "Portfolio"},
                ],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["auto_fill_count"] == 1
    assert payload["review_count"] == 1
    assert payload["submit_allowed"] is False
    assert [item["field_id"] for item in payload["pending_questions"]] == [
        "salary",
        "portfolio",
    ]
    assert map_fields.call_args.kwargs["use_llm"] is False


def test_extension_analysis_saves_memory_and_cv_reuses_it(client):
    with patch("app.main.analyze_job", return_value=_analysis()), patch(
        "app.main.get_analysis_questions", return_value=[]
    ):
        analysis_response = client.post(
            "/extension/analyze-page",
            json={
                "platform": "linkedin",
                "url": VACANCY_URL,
                "company": "Example Co",
                "role": "QA Engineer",
                "job_text": JOB_TEXT,
                "save_application": True,
            },
        )

    assert analysis_response.status_code == 200
    application_id = analysis_response.json()["application"]["id"]

    with patch("app.main.generate_tailored_cv", return_value=_linkedin_cv()) as generate_cv:
        cv_response = client.post(
            "/extension/generate-cv",
            json={
                "platform": "linkedin",
                "url": VACANCY_URL,
                "application_id": application_id,
                "company": "Example Co",
                "role": "QA Engineer",
                "job_text": JOB_TEXT,
            },
        )

    assert cv_response.status_code == 200
    payload = cv_response.json()
    assert payload["application_id"] == application_id
    assert payload["analysis_reused"] is True
    assert payload["artifact_id"] > 0
    assert payload["quality"]["passed"] is True
    assert generate_cv.call_args.kwargs["job_analysis"] == {"keywords": []}

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert metrics.json()["artifacts"] == {
        "total": 1,
        "evaluated": 1,
        "passed": 1,
        "pass_rate": 1.0,
        "average_quality_score": 100.0,
    }
    assert metrics.json()["llm_runs"]["total"] == 0


def test_generation_endpoints_delegate_with_request_contract(client):
    with patch("app.main.generate_answers", return_value="Answers") as answers, patch(
        "app.main.generate_cover_letter", return_value="Letter"
    ) as cover_letter, patch(
        "app.main.generate_tailored_cv", return_value="CV"
    ) as cv:
        answers_response = client.post(
            "/generate-answers",
            json={
                "job_text": JOB_TEXT,
                "questions": ["Do you need visa sponsorship?"],
                "response_language": "en",
            },
        )
        letter_response = client.post(
            "/generate-cover-letter",
            json={
                "job_text": JOB_TEXT,
                "company": "Example Co",
                "role": "QA Engineer",
                "response_language": "en",
            },
        )
        cv_response = client.post(
            "/generate-tailored-cv",
            json={
                "job_text": JOB_TEXT,
                "company": "Example Co",
                "role": "QA Engineer",
                "response_language": "en",
            },
        )

    assert answers_response.json() == {"result": "Answers"}
    assert letter_response.json() == {"result": "Letter"}
    assert cv_response.json() == {"result": "CV"}
    assert answers.call_args.kwargs == {
        "job_text": JOB_TEXT,
        "questions": ["Do you need visa sponsorship?"],
        "response_language": "en",
    }
    assert cover_letter.call_args.kwargs == {
        "job_text": JOB_TEXT,
        "company": "Example Co",
        "role": "QA Engineer",
        "response_language": "en",
    }
    assert cv.call_args.kwargs == {
        "job_text": JOB_TEXT,
        "company": "Example Co",
        "role": "QA Engineer",
        "response_language": "en",
    }


def test_analyze_and_save_keeps_generated_values_and_analysis_link(client):
    with patch("app.main.analyze_job", return_value=_analysis()) as analyze, patch(
        "app.main.generate_cover_letter", return_value="Tailored letter"
    ) as cover_letter:
        response = client.post(
            "/analyze-and-save",
            json={
                "job_text": JOB_TEXT,
                "company": "Example Co",
                "role": "QA Engineer",
                "source": "manual",
                "url": VACANCY_URL,
                "response_language": "en",
                "save_application": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["analysis"] == _analysis()
    assert payload["cover_letter"] == "Tailored letter"
    assert payload["application"]["generated_pitch"] == "Relevant QA experience."
    assert payload["application"]["generated_cover_letter"] == "Tailored letter"
    assert payload["application"]["analysis_result"] == "Structured analysis result."
    assert analyze.call_args.kwargs == {"response_language": "en"}
    assert analyze.call_args.args == (JOB_TEXT,)
    assert cover_letter.call_args.kwargs == {
        "job_text": JOB_TEXT,
        "company": "Example Co",
        "role": "QA Engineer",
        "response_language": "en",
    }

    application_id = payload["application"]["id"]
    db = api.app.state.test_session_factory()
    try:
        record = db.query(JobAnalysisRecord).one()
        assert record.application_id == application_id
        assert record.url == VACANCY_URL
        assert json.loads(record.analysis_json) == {"keywords": []}
    finally:
        db.close()


def test_profile_and_import_contracts_handle_data_errors(client):
    with patch("app.main.load_candidate_profile", return_value={"identity": {"name": "Alex"}}), patch(
        "app.main.load_standard_answers", return_value={"visa": "No"}
    ), patch("app.main.load_interview_stories", return_value={"stories": {}}), patch(
        "app.main.load_missing_data", return_value={"questions": {}}
    ):
        profile = client.get("/profile")

    assert profile.status_code == 200
    assert profile.json()["profile"]["identity"]["name"] == "Alex"

    with patch("app.main.seed_from_data_files", return_value=4) as seed, patch(
        "app.main.sync_candidate_facts", return_value=9
    ) as sync:
        imported = client.post("/import-profile")

    assert imported.status_code == 200
    assert imported.json()["imported_learned_answers"] == 4
    assert imported.json()["candidate_facts"] == 9
    assert seed.call_args.kwargs == {"replace_existing": False}
    assert sync.call_count == 1

    with patch(
        "app.main.load_candidate_profile", side_effect=ProfileDataError("Profile missing")
    ):
        unavailable = client.get("/profile")

    assert unavailable.status_code == 503
    assert unavailable.json() == {
        "detail": "Profile missing",
        "hint": "Run: python scripts/setup_profile_data.py",
    }


def test_metrics_aggregates_runs_and_artifacts(client):
    db = api.app.state.test_session_factory()
    try:
        db.add_all(
            [
                LLMRun(
                    task="analysis",
                    model="test",
                    status="ok",
                    prompt_chars=100,
                    total_duration_ns=120_000_000,
                    created_at="2026-01-01T00:00:00+00:00",
                ),
                LLMRun(
                    task="analysis",
                    model="test",
                    status="error",
                    prompt_chars=120,
                    error="offline",
                    created_at="2026-01-01T00:00:00+00:00",
                ),
                GeneratedArtifact(
                    artifact_type="cv",
                    platform="linkedin",
                    content="CV",
                    model="test",
                    prompt_version="test",
                    quality_score=88.5,
                    quality_passed=True,
                    created_at="2026-01-01T00:00:00+00:00",
                ),
                GeneratedArtifact(
                    artifact_type="cv",
                    platform="linkedin",
                    content="CV pending review",
                    model="test",
                    prompt_version="test",
                    quality_score=None,
                    quality_passed=None,
                    created_at="2026-01-01T00:00:00+00:00",
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.json() == {
        "llm_runs": {
            "total": 2,
            "successful": 1,
            "success_rate": 0.5,
            "average_duration_ms": 120.0,
        },
        "artifacts": {
            "total": 2,
            "evaluated": 1,
            "passed": 1,
            "pass_rate": 1.0,
            "average_quality_score": 88.5,
        },
    }


def test_delete_application_removes_its_analysis_and_artifacts(client):
    db = api.app.state.test_session_factory()
    try:
        application = Application(
            company="Example Co",
            role="QA Engineer",
            source="test",
            url=VACANCY_URL,
            status="draft",
        )
        db.add(application)
        db.commit()
        db.refresh(application)
        analysis = JobAnalysisRecord(
            application_id=application.id,
            url=VACANCY_URL,
            job_hash="job-hash",
            model="test",
            prompt_version="test",
            analysis_json="{}",
            rendered_text="Analysis",
            created_at="2026-01-01T00:00:00+00:00",
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        db.add(
            GeneratedArtifact(
                application_id=application.id,
                analysis_id=analysis.id,
                artifact_type="cv",
                platform="linkedin",
                content="CV",
                model="test",
                prompt_version="test",
                created_at="2026-01-01T00:00:00+00:00",
            )
        )
        db.commit()

        response = client.delete(f"/applications/{application.id}")
        db.expire_all()
        assert response.status_code == 200
        assert db.query(Application).count() == 0
        assert db.query(JobAnalysisRecord).count() == 0
        assert db.query(GeneratedArtifact).count() == 0
    finally:
        db.close()
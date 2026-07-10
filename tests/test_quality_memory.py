import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.memory import (
    analysis_dict,
    latest_job_analysis,
    retrieve_candidate_context,
    save_generated_artifact,
    save_job_analysis,
)
from app.quality import evaluate_cv
from app.storage import Application, Base, CandidateFact


class QualityTests(unittest.TestCase):
    def test_flags_unconfirmed_vacancy_keyword(self):
        result = evaluate_cv(
            "PROFESSIONAL SUMMARY\nPostman and Kubernetes testing\n"
            "TECHNICAL SKILLS\nPostman, Kubernetes\n"
            "PROFESSIONAL EXPERIENCE\nAPI testing\nLANGUAGES\nEnglish",
            platform="linkedin",
            analysis={"keywords": ["Postman", "Kubernetes"]},
            confirmed_facts_text="tools: Postman\nexperience: API testing",
        )

        self.assertFalse(result["passed"])
        self.assertEqual(result["requirement_coverage"], 1.0)
        self.assertEqual(result["unsupported_keywords"], ["Kubernetes"])

    def test_hh_format_rules(self):
        result = evaluate_cv(
            "**Добрый день!**\n- Короткий текст",
            platform="hh",
            analysis={"keywords": []},
            confirmed_facts_text="",
        )

        self.assertIn("markdown_found", result["format_violations"])
        self.assertIn("hh_too_short", result["format_violations"])
        self.assertIn("hh_bullets_found", result["format_violations"])


class MemoryPersistenceTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.application = Application(
            company="Example",
            role="QA Engineer",
            source="test",
            url="https://example.test/job/1",
            status="draft",
        )
        self.db.add(self.application)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_analysis_and_artifact_keep_the_same_application_context(self):
        job_text = "QA Engineer requiring API testing and Postman."
        saved = save_job_analysis(
            self.db,
            analysis={"keywords": ["Postman"], "fit_score": 80},
            rendered_text="Fit 80",
            job_text=job_text,
            application_id=self.application.id,
            url=self.application.url,
        )
        loaded = latest_job_analysis(
            self.db,
            application_id=self.application.id,
            url=self.application.url,
            job_text=job_text,
        )
        self.assertEqual(loaded.id, saved.id)
        self.assertEqual(analysis_dict(loaded)["keywords"], ["Postman"])

        artifact = save_generated_artifact(
            self.db,
            application_id=self.application.id,
            analysis_id=loaded.id,
            artifact_type="cv",
            platform="linkedin",
            url=self.application.url,
            content="Generated CV",
            model="test-model",
            quality={"score": 90, "passed": True},
        )
        self.assertEqual(artifact.analysis_id, saved.id)
        self.assertTrue(artifact.quality_passed)


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.db.add_all(
            [
                CandidateFact(
                    fact_key="identity.name",
                    category="identity",
                    value_text="Alex Doe",
                    source="candidate_profile",
                    confidence="high",
                    active=True,
                    updated_at="2026-01-01",
                ),
                CandidateFact(
                    fact_key="projects.api.tools.0",
                    category="projects",
                    value_text="Postman",
                    source="candidate_profile",
                    confidence="high",
                    active=True,
                    updated_at="2026-01-01",
                ),
                CandidateFact(
                    fact_key="projects.mobile.tools.0",
                    category="projects",
                    value_text="Appium",
                    source="candidate_profile",
                    confidence="high",
                    active=True,
                    updated_at="2026-01-01",
                ),
            ]
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_retrieves_identity_and_relevant_fact(self):
        context = retrieve_candidate_context(
            self.db,
            "QA vacancy requires API testing with Postman",
            max_chars=1000,
        )

        self.assertIn("identity.name: Alex Doe", context)
        self.assertIn("projects.api.tools.0: Postman", context)
        self.assertNotIn("Appium", context)


if __name__ == "__main__":
    unittest.main()

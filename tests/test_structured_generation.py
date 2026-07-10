import unittest
from unittest.mock import patch

from app.analysis_models import JobAnalysis
from app.analyzer import analyze_job
from app.cv_generator import generate_tailored_cv


def sample_analysis() -> JobAnalysis:
    return JobAnalysis(
        fit_score=78,
        should_apply="yes",
        score_reason="QA role and API stack align.",
        role_type="QA Engineer",
        seniority="middle",
        must_have_requirements=["API testing", "Postman"],
        nice_to_have_requirements=["Python"],
        matching_requirements=["API testing", "Postman"],
        missing_or_weak_requirements=["Python"],
        risks=[],
        keywords=["API testing", "Postman"],
        application_strategy="Lead with API testing experience.",
        short_pitch="QA engineer with relevant API testing experience.",
        questions_for_candidate=[],
    )


class StructuredAnalysisTests(unittest.TestCase):
    @patch("app.analyzer.candidate_context_for_query", return_value="tools: Postman")
    @patch("app.analyzer.ask_llm")
    def test_analysis_returns_structured_and_rendered_contract(
        self,
        ask_llm_mock,
        _context_mock,
    ):
        ask_llm_mock.return_value = sample_analysis().model_dump_json()

        result = analyze_job(
            "QA Engineer role requiring API testing and Postman experience.",
            response_language="en",
        )

        self.assertEqual(result["fit_score"], 78)
        self.assertEqual(result["structured"]["keywords"], ["API testing", "Postman"])
        self.assertIn("## Fit Score", result["result"])
        self.assertEqual(
            ask_llm_mock.call_args.kwargs["response_schema"],
            JobAnalysis,
        )


class CvMemoryTests(unittest.TestCase):
    @patch("app.cv_generator.candidate_context_for_query", return_value="tools: Postman")
    @patch("app.cv_generator.ask_llm", return_value="Generated CV")
    def test_saved_analysis_is_included_in_cv_prompt(
        self,
        ask_llm_mock,
        _context_mock,
    ):
        analysis = sample_analysis().model_dump()

        result = generate_tailored_cv(
            "QA Engineer with Postman.",
            company="Example",
            role="QA Engineer",
            platform="linkedin",
            job_analysis=analysis,
        )

        self.assertEqual(result, "Generated CV")
        user_prompt = ask_llm_mock.call_args.args[1]
        self.assertIn("Structured vacancy analysis from memory", user_prompt)
        self.assertIn('"Postman"', user_prompt)
        self.assertEqual(
            ask_llm_mock.call_args.kwargs["task"],
            "generate_cv:linkedin",
        )


if __name__ == "__main__":
    unittest.main()

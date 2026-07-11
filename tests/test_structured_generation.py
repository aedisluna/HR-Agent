import json
import unittest
from unittest.mock import patch

from app.analysis_models import JobAnalysis, RequirementAssessment
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
        requirement_assessments=[
            RequirementAssessment(
                requirement="API testing",
                status="matched",
                evidence=["projects.api.testing"],
                reason="Confirmed API testing experience.",
            ),
            RequirementAssessment(
                requirement="Postman",
                status="matched",
                evidence=["projects.api.tools.0"],
                reason="Postman is present in confirmed project tools.",
            ),
        ],
        risks=[],
        keywords=["API testing", "Postman"],
        application_strategy="Lead with API testing experience.",
        short_pitch="QA engineer with relevant API testing experience.",
        questions_for_candidate=[],
    )


class StructuredAnalysisTests(unittest.TestCase):
    @patch(
        "app.analyzer.candidate_context_for_query",
        return_value="projects.api.testing: API testing\nprojects.api.tools.0: Postman",
    )
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
        self.assertEqual(len(result["structured"]["matching_requirements"]), 2)
        self.assertIn("Confirmed API testing experience", result["result"])
        self.assertIn("## Fit Score", result["result"])
        self.assertEqual(
            ask_llm_mock.call_args.kwargs["response_schema"],
            JobAnalysis,
        )


    @patch(
        "app.analyzer.candidate_context_for_query",
        return_value="projects.api.testing: API testing\nprojects.api.tools.0: Postman",
    )
    @patch("app.analyzer.ask_llm")
    def test_inconsistent_high_score_is_retried(
        self,
        ask_llm_mock,
        _context_mock,
    ):
        invalid = sample_analysis().model_dump()
        invalid["requirement_assessments"] = [
            {
                "requirement": "API testing",
                "status": "unknown",
                "evidence": [],
                "reason": "Not enough evidence.",
            },
            {
                "requirement": "Postman",
                "status": "unknown",
                "evidence": [],
                "reason": "Not enough evidence.",
            },
        ]
        ask_llm_mock.side_effect = [
            json.dumps(invalid),
            sample_analysis().model_dump_json(),
        ]

        result = analyze_job(
            "QA Engineer role requiring API testing and Postman experience.",
            response_language="en",
        )

        self.assertEqual(ask_llm_mock.call_count, 2)
        self.assertEqual(
            ask_llm_mock.call_args_list[1].kwargs["task"],
            "analyze_job_retry",
        )
        self.assertEqual(len(result["structured"]["matching_requirements"]), 2)


    @patch(
        "app.analyzer.candidate_context_for_query",
        return_value="projects.api.testing: API testing\nprojects.api.tools.0: Postman",
    )
    @patch("app.analyzer.ask_llm")
    def test_unavailable_evidence_key_is_retried(
        self,
        ask_llm_mock,
        _context_mock,
    ):
        invalid = sample_analysis().model_dump()
        invalid["requirement_assessments"][0]["evidence"] = ["invented.fact"]
        ask_llm_mock.side_effect = [
            json.dumps(invalid),
            sample_analysis().model_dump_json(),
        ]

        result = analyze_job(
            "QA Engineer role requiring API testing and Postman experience.",
            response_language="en",
        )

        self.assertEqual(ask_llm_mock.call_count, 2)
        self.assertEqual(len(result["structured"]["matching_requirements"]), 2)


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

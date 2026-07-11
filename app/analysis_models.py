import re
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


def _normalize_requirement(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


class RequirementAssessment(BaseModel):
    """Evidence-backed classification of one vacancy requirement."""

    requirement: str = Field(min_length=1)
    status: Literal["matched", "missing", "unknown"]
    evidence: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def matched_requires_evidence(self):
        if self.status == "matched" and not self.evidence:
            raise ValueError("matched requirement must reference candidate fact evidence")
        return self


class JobAnalysis(BaseModel):
    """Stable machine-readable vacancy analysis used by downstream generators."""

    fit_score: int = Field(ge=0, le=100)
    should_apply: Literal["yes", "maybe", "no"]
    score_reason: str = Field(min_length=1)
    role_type: str = Field(min_length=1)
    seniority: str | None = None
    must_have_requirements: list[str] = Field(min_length=1)
    nice_to_have_requirements: list[str] = Field(default_factory=list)
    requirement_assessments: list[RequirementAssessment] = Field(min_length=1)
    risks: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(min_length=1)
    application_strategy: str = Field(min_length=1)
    short_pitch: str = Field(min_length=1)
    questions_for_candidate: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_consistency(self):
        assessments = {
            _normalize_requirement(item.requirement): item
            for item in self.requirement_assessments
        }
        unassessed = [
            requirement
            for requirement in self.must_have_requirements
            if _normalize_requirement(requirement) not in assessments
        ]
        if unassessed:
            raise ValueError(
                "every must-have requirement must have an assessment; missing: "
                + "; ".join(unassessed)
            )

        matched_count = sum(
            item.status == "matched" for item in self.requirement_assessments
        )
        missing_count = sum(
            item.status == "missing" for item in self.requirement_assessments
        )

        if self.fit_score >= 66 and matched_count == 0:
            raise ValueError("fit_score >= 66 requires at least one matched requirement")
        if self.fit_score >= 66 and self.should_apply != "yes":
            raise ValueError("fit_score >= 66 requires should_apply=yes")
        if 45 <= self.fit_score <= 65 and self.should_apply != "maybe":
            raise ValueError("fit_score 45-65 requires should_apply=maybe")
        if self.fit_score < 45 and self.should_apply != "no":
            raise ValueError("fit_score below 45 requires should_apply=no")
        if missing_count >= 3 and self.fit_score > 45:
            raise ValueError("three missing must-haves cap fit_score at 45")
        return self


def matching_requirements(analysis: JobAnalysis) -> list[str]:
    return [
        f"{item.requirement} — {item.reason}"
        for item in analysis.requirement_assessments
        if item.status == "matched"
    ]


def missing_or_weak_requirements(analysis: JobAnalysis) -> list[str]:
    rows: list[str] = []
    for item in analysis.requirement_assessments:
        if item.status == "missing":
            rows.append(f"{item.requirement} — {item.reason}")
        elif item.status == "unknown":
            rows.append(f"{item.requirement} — needs confirmation: {item.reason}")
    return rows


def analysis_payload(analysis: JobAnalysis) -> dict[str, Any]:
    """Serialize the schema plus compatibility lists used by existing consumers."""

    payload = analysis.model_dump()
    payload["matching_requirements"] = matching_requirements(analysis)
    payload["missing_or_weak_requirements"] = missing_or_weak_requirements(analysis)
    return payload


def _bullets(items: list[str], empty_message: str) -> str:
    return "\n".join(f"- {item}" for item in items) if items else f"- {empty_message}"


def render_job_analysis(analysis: JobAnalysis) -> str:
    """Render structured analysis for the existing extension/UI contract."""

    return f"""## Fit Score
{analysis.fit_score}/100 — {analysis.score_reason}

## Should Apply?
{analysis.should_apply}

## Matching Requirements
{_bullets(matching_requirements(analysis), "No confirmed matches found.")}

## Missing or Weak Requirements
{_bullets(missing_or_weak_requirements(analysis), "No material gaps identified.")}

## Risks
{_bullets(analysis.risks, "No material risks identified.")}

## Application Strategy
{analysis.application_strategy}

## Short Pitch
{analysis.short_pitch}

## Questions for the Candidate
{_bullets(analysis.questions_for_candidate, "No additional questions.")}"""

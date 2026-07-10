from typing import Literal

from pydantic import BaseModel, Field


class JobAnalysis(BaseModel):
    """Stable machine-readable vacancy analysis used by downstream generators."""

    fit_score: int = Field(ge=0, le=100)
    should_apply: Literal["yes", "maybe", "no"]
    score_reason: str
    role_type: str
    seniority: str | None = None
    must_have_requirements: list[str] = Field(min_length=1)
    nice_to_have_requirements: list[str] = Field(default_factory=list)
    matching_requirements: list[str] = Field(default_factory=list)
    missing_or_weak_requirements: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(min_length=1)
    application_strategy: str
    short_pitch: str
    questions_for_candidate: list[str] = Field(default_factory=list)


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- None"


def render_job_analysis(analysis: JobAnalysis) -> str:
    """Render structured analysis for the existing extension/UI contract."""

    return f"""## Fit Score
{analysis.fit_score}/100 — {analysis.score_reason}

## Should Apply?
{analysis.should_apply}

## Matching Requirements
{_bullets(analysis.matching_requirements)}

## Missing or Weak Requirements
{_bullets(analysis.missing_or_weak_requirements)}

## Risks
{_bullets(analysis.risks)}

## Application Strategy
{analysis.application_strategy}

## Short Pitch
{analysis.short_pitch}

## Questions for the Candidate
{_bullets(analysis.questions_for_candidate)}"""

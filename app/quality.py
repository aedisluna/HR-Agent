"""Deterministic first-pass quality checks for generated CV artifacts."""

from __future__ import annotations

import re
from typing import Any


def _contains(text: str, phrase: str) -> bool:
    normalized = re.sub(r"\s+", " ", phrase.strip())
    if not normalized:
        return False
    pattern = rf"(?<!\w){re.escape(normalized)}(?!\w)"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def evaluate_cv(
    cv_text: str,
    *,
    platform: str | None,
    analysis: dict[str, Any] | None,
    confirmed_facts_text: str,
) -> dict[str, Any]:
    normalized_platform = (platform or "generic").lower()
    length = len(cv_text.strip())
    violations: list[str] = []

    markdown_found = bool(
        re.search(r"^#{1,6}\s|\*\*|^---+$", cv_text, flags=re.MULTILINE)
    )
    if markdown_found:
        violations.append("markdown_found")

    if normalized_platform == "hh":
        if length < 700:
            violations.append("hh_too_short")
        if length > 1500:
            violations.append("hh_too_long")
        if re.search(r"(?m)^\s*[-*•]\s+", cv_text):
            violations.append("hh_bullets_found")
    elif normalized_platform == "linkedin":
        for header in (
            "PROFESSIONAL SUMMARY",
            "TECHNICAL SKILLS",
            "PROFESSIONAL EXPERIENCE",
            "LANGUAGES",
        ):
            if header not in cv_text:
                violations.append(f"missing_section:{header.lower().replace(' ', '_')}")

    keywords = [
        str(item).strip()
        for item in (analysis or {}).get("keywords", [])
        if str(item).strip()
    ]
    confirmed_keywords = [
        keyword for keyword in keywords if _contains(confirmed_facts_text, keyword)
    ]
    covered_keywords = [
        keyword for keyword in confirmed_keywords if _contains(cv_text, keyword)
    ]
    unsupported_keywords = [
        keyword
        for keyword in keywords
        if _contains(cv_text, keyword) and not _contains(confirmed_facts_text, keyword)
    ]

    coverage = (
        len(covered_keywords) / len(confirmed_keywords)
        if confirmed_keywords
        else None
    )

    score = 100.0
    score -= min(40, len(violations) * 10)
    score -= min(45, len(unsupported_keywords) * 15)
    if coverage is not None and coverage < 0.5:
        score -= round((0.5 - coverage) * 40, 2)
    score = max(0.0, round(score, 2))
    passed = not unsupported_keywords and not violations and score >= 70

    return {
        "score": score,
        "passed": passed,
        "length_chars": length,
        "format_violations": violations,
        "confirmed_keyword_count": len(confirmed_keywords),
        "covered_confirmed_keywords": covered_keywords,
        "requirement_coverage": round(coverage, 3) if coverage is not None else None,
        "unsupported_keywords": unsupported_keywords,
    }

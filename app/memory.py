"""SQLite-backed memory and retrieval for vacancy-specific generation."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.config import MODEL_FAST
from app.profile import load_candidate_profile, load_resume, load_skill_catalog
from app.storage import (
    Application,
    CandidateFact,
    GeneratedArtifact,
    JobAnalysisRecord,
    SessionLocal,
    init_db,
    utc_now_iso,
)

ANALYSIS_PROMPT_VERSION = "job-analysis-v3"
CV_PROMPT_VERSION = "tailored-cv-v2"

_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9+#.]{2,}")
_ALWAYS_INCLUDE = {"identity", "positioning", "professional_summary", "role_boundaries"}
_ANALYSIS_PRIORITY_CATEGORIES = {
    "identity",
    "positioning",
    "professional_summary",
    "role_boundaries",
    "experience",
    "projects",
    "resume",
    "current_project_details",
    "skills",
}
_STOPWORDS = {
    "and", "the", "with", "for", "from", "this", "that", "или", "для", "как",
    "при", "это", "что", "опыт", "работы", "работа", "требования",
}


def job_text_hash(job_text: str) -> str:
    normalized = re.sub(r"\s+", " ", job_text).strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _flatten(value: Any, path: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            rows.extend(_flatten(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.extend(_flatten(child, f"{path}.{index}"))
    elif value is not None and str(value).strip():
        rows.append((path, str(value).strip()))
    return rows


def _normalized_skill_catalog(
    catalog: list[dict[str, Any]],
) -> list[tuple[str, tuple[str, ...]]]:
    normalized: list[tuple[str, tuple[str, ...]]] = []
    for item in catalog:
        label = str(item.get("label", "")).strip()
        aliases = item.get("aliases", [])
        if not label or not isinstance(aliases, list):
            continue
        needles = tuple(
            alias.lower()
            for alias in [label, *aliases]
            if isinstance(alias, str) and alias.strip()
        )
        if needles:
            normalized.append((label, needles))
    return normalized


def _build_skills_inventory(
    profile: dict[str, Any],
    resume: str,
    *,
    catalog: list[dict[str, Any]] | None = None,
) -> str:
    blob = "\n".join(value for _, value in _flatten(profile, "")).lower()
    blob = f"{blob}\n{resume.lower()}"

    matched: list[str] = []
    source_catalog = catalog if catalog is not None else load_skill_catalog()
    for label, needles in _normalized_skill_catalog(source_catalog):
        if any(needle in blob for needle in needles):
            matched.append(label)
    return "; ".join(matched)

def sync_candidate_facts(db: Session) -> int:
    """Refresh confirmed file-backed facts without touching learned user answers."""

    now = utc_now_iso()
    rows = [
        {
            "fact_key": path,
            "category": path.split(".", 1)[0],
            "value_text": value,
            "source": "candidate_profile",
        }
        for path, value in _flatten(load_candidate_profile(), "")
    ]

    resume_parts = [
        part.strip()
        for part in re.split(
            r"\n\s*\n|^#{1,6}\s+",
            load_resume(),
            flags=re.MULTILINE,
        )
        if part.strip()
    ]
    rows.extend(
        {
            "fact_key": f"resume.{index}",
            "category": "resume",
            "value_text": part,
            "source": "resume",
        }
        for index, part in enumerate(resume_parts)
    )

    skills_inventory = _build_skills_inventory(load_candidate_profile(), load_resume())
    if skills_inventory:
        rows.append(
            {
                "fact_key": "skills_inventory",
                "category": "skills",
                "value_text": skills_inventory,
                "source": "derived",
            }
        )

    db.query(CandidateFact).filter(
        CandidateFact.source.in_(["candidate_profile", "resume", "derived"])
    ).delete(synchronize_session=False)
    for row in rows:
        db.add(CandidateFact(**row, confidence="high", active=True, updated_at=now))
    db.commit()
    return len(rows)


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in _TOKEN_RE.findall(text)
        if token.lower() not in _STOPWORDS
    }


def retrieve_candidate_context(
    db: Session,
    query: str,
    *,
    max_chars: int = 12000,
    exclude_key_prefixes: tuple[str, ...] = (),
    exclude_value_markers: tuple[str, ...] = (),
) -> str:
    facts = db.query(CandidateFact).filter(CandidateFact.active.is_(True)).all()
    if not facts:
        sync_candidate_facts(db)
        facts = db.query(CandidateFact).filter(CandidateFact.active.is_(True)).all()

    query_tokens = _tokens(query)
    ranked: list[tuple[int, str]] = []
    for fact in facts:
        if any(fact.fact_key.startswith(prefix) for prefix in exclude_key_prefixes):
            continue
        if any(marker in fact.value_text for marker in exclude_value_markers):
            continue
        fact_text = f"{fact.fact_key}: {fact.value_text}"
        overlap = len(query_tokens & _tokens(fact_text))
        score = overlap * 10
        if fact.category in _ALWAYS_INCLUDE:
            score += 100
        if overlap or score:
            ranked.append((score, fact_text))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    selected: list[str] = []
    size = 0
    for _, fact_text in ranked:
        next_size = size + len(fact_text) + 1
        if next_size > max_chars:
            continue
        selected.append(fact_text)
        size = next_size
    return "\n".join(selected)


def retrieve_candidate_context_for_analysis(
    db: Session,
    query: str,
    *,
    max_chars: int = 16000,
) -> str:
    facts = db.query(CandidateFact).filter(CandidateFact.active.is_(True)).all()
    if not facts:
        sync_candidate_facts(db)
        facts = db.query(CandidateFact).filter(CandidateFact.active.is_(True)).all()

    priority = [fact for fact in facts if fact.category in _ANALYSIS_PRIORITY_CATEGORIES]
    other = [fact for fact in facts if fact.category not in _ANALYSIS_PRIORITY_CATEGORIES]

    selected: list[str] = []
    size = 0
    for fact in sorted(priority, key=lambda item: item.fact_key):
        line = f"{fact.fact_key}: {fact.value_text}"
        selected.append(line)
        size += len(line) + 1

    query_tokens = _tokens(query)
    ranked_other: list[tuple[int, str]] = []
    for fact in other:
        fact_text = f"{fact.fact_key}: {fact.value_text}"
        overlap = len(query_tokens & _tokens(fact_text))
        if overlap:
            ranked_other.append((overlap * 10, fact_text))

    ranked_other.sort(key=lambda item: (-item[0], item[1]))
    for _, fact_text in ranked_other:
        next_size = size + len(fact_text) + 1
        if next_size > max_chars:
            continue
        selected.append(fact_text)
        size = next_size

    if size <= max_chars:
        return "\n".join(selected)

    trimmed: list[str] = []
    running = 0
    for line in selected:
        next_size = running + len(line) + 1
        if next_size > max_chars:
            break
        trimmed.append(line)
        running = next_size
    return "\n".join(trimmed)


def candidate_context_for_query(
    query: str,
    *,
    max_chars: int = 12000,
    exclude_key_prefixes: tuple[str, ...] = (),
    exclude_value_markers: tuple[str, ...] = (),
) -> str:
    init_db()
    db = SessionLocal()
    try:
        return retrieve_candidate_context(
            db,
            query,
            max_chars=max_chars,
            exclude_key_prefixes=exclude_key_prefixes,
            exclude_value_markers=exclude_value_markers,
        )
    finally:
        db.close()


def candidate_context_for_analysis(query: str, *, max_chars: int = 16000) -> str:
    init_db()
    db = SessionLocal()
    try:
        return retrieve_candidate_context_for_analysis(db, query, max_chars=max_chars)
    finally:
        db.close()


def all_candidate_fact_text(db: Session) -> str:
    facts = db.query(CandidateFact).filter(CandidateFact.active.is_(True)).all()
    if not facts:
        sync_candidate_facts(db)
        facts = db.query(CandidateFact).filter(CandidateFact.active.is_(True)).all()
    return "\n".join(f"{item.fact_key}: {item.value_text}" for item in facts)


def find_application(
    db: Session,
    *,
    application_id: int | None = None,
    url: str | None = None,
) -> Application | None:
    if application_id is not None:
        application = db.get(Application, application_id)
        if application:
            return application
    if url:
        return (
            db.query(Application)
            .filter(Application.url == url)
            .order_by(Application.id.desc())
            .first()
        )
    return None


def save_job_analysis(
    db: Session,
    *,
    analysis: dict[str, Any],
    rendered_text: str,
    job_text: str,
    application_id: int | None,
    url: str | None,
    model: str = MODEL_FAST,
) -> JobAnalysisRecord:
    record = JobAnalysisRecord(
        application_id=application_id,
        url=url,
        job_hash=job_text_hash(job_text),
        model=model,
        prompt_version=ANALYSIS_PROMPT_VERSION,
        analysis_json=json.dumps(analysis, ensure_ascii=False),
        rendered_text=rendered_text,
        created_at=utc_now_iso(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def latest_job_analysis(
    db: Session,
    *,
    application_id: int | None,
    url: str | None,
    job_text: str,
) -> JobAnalysisRecord | None:
    query = db.query(JobAnalysisRecord).filter(
        JobAnalysisRecord.job_hash == job_text_hash(job_text)
    )
    if application_id is not None:
        query = query.filter(JobAnalysisRecord.application_id == application_id)
    elif url:
        query = query.filter(JobAnalysisRecord.url == url)
    return query.order_by(JobAnalysisRecord.id.desc()).first()


def analysis_dict(record: JobAnalysisRecord | None) -> dict[str, Any] | None:
    if not record:
        return None
    try:
        return json.loads(record.analysis_json)
    except json.JSONDecodeError:
        return None


def save_generated_artifact(
    db: Session,
    *,
    application_id: int | None,
    analysis_id: int | None,
    artifact_type: str,
    platform: str,
    url: str | None,
    content: str,
    model: str,
    quality: dict[str, Any],
) -> GeneratedArtifact:
    artifact = GeneratedArtifact(
        application_id=application_id,
        analysis_id=analysis_id,
        artifact_type=artifact_type,
        platform=platform,
        url=url,
        content=content,
        model=model,
        prompt_version=CV_PROMPT_VERSION,
        quality_score=quality.get("score"),
        quality_passed=quality.get("passed"),
        quality_json=json.dumps(quality, ensure_ascii=False),
        created_at=utc_now_iso(),
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact

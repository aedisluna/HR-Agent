from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DATA_DIR


class Base(DeclarativeBase):
    pass


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company = Column(String, nullable=False)
    role = Column(String, nullable=False)
    source = Column(String, nullable=False)
    url = Column(String, nullable=True)
    status = Column(String, nullable=False, default="draft")
    fit_score = Column(Integer, nullable=True)
    applied_at = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    generated_pitch = Column(Text, nullable=True)
    generated_cover_letter = Column(Text, nullable=True)
    raw_job_text = Column(Text, nullable=True)
    analysis_result = Column(Text, nullable=True)


class LearnedAnswer(Base):
    __tablename__ = "learned_answers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    question_pattern = Column(String, nullable=False)
    answer = Column(Text, nullable=False)
    confidence = Column(String, nullable=False, default="medium")
    requires_confirmation = Column(Boolean, nullable=False, default=True)


class CandidateFact(Base):
    """A confirmed, addressable profile fact available to prompt retrieval."""

    __tablename__ = "candidate_facts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fact_key = Column(String, nullable=False, unique=True, index=True)
    category = Column(String, nullable=False, index=True)
    value_text = Column(Text, nullable=False)
    source = Column(String, nullable=False, index=True)
    confidence = Column(String, nullable=False, default="high")
    active = Column(Boolean, nullable=False, default=True)
    updated_at = Column(String, nullable=False)


class JobAnalysisRecord(Base):
    """Versioned structured analysis tied to an application/vacancy."""

    __tablename__ = "job_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=True, index=True)
    url = Column(String, nullable=True, index=True)
    job_hash = Column(String, nullable=False, index=True)
    model = Column(String, nullable=False)
    prompt_version = Column(String, nullable=False)
    analysis_json = Column(Text, nullable=False)
    rendered_text = Column(Text, nullable=False)
    created_at = Column(String, nullable=False)


class GeneratedArtifact(Base):
    """A generated CV/letter plus the automatic evaluation attached to it."""

    __tablename__ = "generated_artifacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=True, index=True)
    analysis_id = Column(Integer, ForeignKey("job_analyses.id"), nullable=True)
    artifact_type = Column(String, nullable=False, index=True)
    platform = Column(String, nullable=False, default="generic")
    url = Column(String, nullable=True, index=True)
    content = Column(Text, nullable=False)
    model = Column(String, nullable=False)
    prompt_version = Column(String, nullable=False)
    quality_score = Column(Float, nullable=True)
    quality_passed = Column(Boolean, nullable=True)
    quality_json = Column(Text, nullable=True)
    created_at = Column(String, nullable=False)


class LLMRun(Base):
    """Operational telemetry returned by Ollama for every model call."""

    __tablename__ = "llm_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task = Column(String, nullable=False, index=True)
    model = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, index=True)
    prompt_chars = Column(Integer, nullable=False)
    output_chars = Column(Integer, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    total_duration_ns = Column(Integer, nullable=True)
    load_duration_ns = Column(Integer, nullable=True)
    prompt_eval_duration_ns = Column(Integer, nullable=True)
    eval_duration_ns = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(String, nullable=False)


def get_database_url() -> str:
    db_path = DATA_DIR / "applications.db"
    return f"sqlite:///{db_path.as_posix()}"


engine = create_engine(
    get_database_url(),
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

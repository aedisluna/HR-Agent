from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Integer, String, Text, create_engine
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

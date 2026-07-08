import logging
import time
from contextlib import asynccontextmanager

import yaml
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app.analyzer import analyze_job, generate_cover_letter
from app.answer_generator import generate_answers
from app.cv_generator import generate_tailored_cv
from app.config import APP_VERSION, APPLICATION_STATUSES, MODEL, MODEL_FAST, PROJECT_ROOT
from app.llm import LLMError
from app.logging_setup import BACKEND_LOG, LAUNCHER_LOG, clear_log_files, read_log_tail, setup_logging
from app.platforms.ats import map_form_fields
from app.profile import (
    ProfileDataError,
    load_candidate_profile,
    load_interview_stories,
    load_missing_data,
    load_standard_answers,
)
from app.extension_service import (
    get_missing_profile_questions,
    get_analysis_questions,
    mappings_need_user_input,
    track_application,
    upsert_learned_answer,
)
from app.seed_profile import seed_from_data_files
from app.schemas import (
    AnswerRequest,
    ApplicationCreate,
    ApplicationResponse,
    ApplicationUpdate,
    CoverLetterRequest,
    ExtensionAnalyzeRequest,
    ExtensionFillFormRequest,
    ExtensionGenerateCvRequest,
    ExtensionSaveAnswerRequest,
    ExtensionTrackRequest,
    FullAnalysisRequest,
    JobAnalyzeRequest,
    LearnedAnswerCreate,
    LearnedAnswerResponse,
    TailoredCvRequest,
)
from app.storage import Application, LearnedAnswer, SessionLocal, get_db, init_db, utc_now_iso

setup_logging()
logger = logging.getLogger("hr_agent.api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        learned_count = db.query(LearnedAnswer).count()
        if learned_count == 0:
            seeded = seed_from_data_files(replace_existing=True)
            logger.info("Seeded %s learned answers on first run", seeded)
        else:
            logger.info("Learned answers already present: %s rows", learned_count)
    except ProfileDataError as exc:
        logger.warning("Profile seed skipped: %s", exc)
    finally:
        db.close()
    logger.info(
        "HR Agent API started (version %s, model=%s, fast=%s)",
        APP_VERSION,
        MODEL,
        MODEL_FAST,
    )
    yield


app = FastAPI(
    title="Local Job Application Assistant",
    description="Local AI assistant for job analysis, answers, and application tracking.",
    version=APP_VERSION,
    lifespan=lifespan,
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/debug/logs":
            return await call_next(request)

        started = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "%s %s -> %s (%.0fms)",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
            return response
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            logger.exception(
                "%s %s failed after %.0fms",
                request.method,
                request.url.path,
                duration_ms,
            )
            raise


app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8001",
        "http://localhost:8001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _handle_llm_error(exc: LLMError) -> HTTPException:
    return HTTPException(status_code=503, detail=str(exc))


@app.exception_handler(ProfileDataError)
async def profile_data_error_handler(_request: Request, exc: ProfileDataError):
    return JSONResponse(
        status_code=503,
        content={
            "detail": str(exc),
            "hint": "Run: python scripts/setup_profile_data.py",
        },
    )


@app.exception_handler(yaml.YAMLError)
async def yaml_error_handler(_request: Request, exc: yaml.YAMLError):
    return JSONResponse(
        status_code=422,
        content={"detail": f"Invalid YAML in profile data: {exc}"},
    )


def _log_path_label(path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return path.name


@app.get("/", response_class=HTMLResponse)
def root():
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Job Application Assistant</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 720px; margin: 48px auto; padding: 0 24px; line-height: 1.5; }}
    h1 {{ margin-bottom: 0.25rem; }}
    .muted {{ color: #666; }}
    a {{ color: #2563eb; }}
    ul {{ padding-left: 1.25rem; }}
    code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Local Job Application Assistant</h1>
  <p class="muted">API is running. Model: <code>{MODEL}</code></p>
  <ul>
    <li><a href="/docs">Swagger UI</a> — test endpoints</li>
    <li><a href="/redoc">ReDoc</a> — API documentation</li>
    <li><a href="/health">/health</a> — status check</li>
    <li><a href="/profile">/profile</a> — candidate profile JSON</li>
    <li><a href="/applications">/applications</a> — saved applications JSON</li>
    <li><a href="/applications/ui">/applications/ui</a> — applications dashboard</li>
    <li><a href="/learned-answers">/learned-answers</a> — standard answers DB</li>
    <li><a href="/debug/logs">/debug/logs</a> — recent backend logs</li>
  </ul>
  <p>For the visual UI, run: <code>streamlit run ui/streamlit_app.py</code></p>
  <p>Browser extension: load unpacked from <code>extension/</code> in Chrome/Brave.</p>
  <p>Launcher (run once per session): <code>python scripts/launcher.py</code></p>
</body>
</html>"""


@app.get("/health")
def health_check():
    return {"status": "ok", "version": APP_VERSION}


@app.get("/debug/logs")
def get_debug_logs(
    source: str = Query(default="all", pattern="^(all|backend|launcher)$"),
    lines: int = Query(default=200, ge=1, le=1000),
):
    backend_lines = read_log_tail(BACKEND_LOG, lines) if source in {"all", "backend"} else []
    launcher_lines = read_log_tail(LAUNCHER_LOG, lines) if source in {"all", "launcher"} else []

    return {
        "source": source,
        "lines": lines,
        "backend": {
            "path": _log_path_label(BACKEND_LOG),
            "exists": BACKEND_LOG.exists(),
            "entries": backend_lines,
        },
        "launcher": {
            "path": _log_path_label(LAUNCHER_LOG),
            "exists": LAUNCHER_LOG.exists(),
            "entries": launcher_lines,
        },
    }


@app.delete("/debug/logs")
def delete_debug_logs(
    source: str = Query(default="all", pattern="^(all|backend|launcher)$"),
):
    cleared = clear_log_files(source)
    return {"cleared": cleared, "source": source}


@app.get("/profile")
def get_profile():
    return {
        "profile": load_candidate_profile(),
        "standard_answers": load_standard_answers(),
        "interview_stories": load_interview_stories(),
        "missing_data": load_missing_data(),
    }


@app.post("/import-profile")
def import_profile():
    count = seed_from_data_files(replace_existing=True)
    return {
        "imported_learned_answers": count,
        "profile_files": [
            "candidate_profile.yaml",
            "standard_answers.yaml",
            "interview_stories.yaml",
            "missing_data.yaml",
        ],
    }


@app.post("/analyze-job")
def analyze_job_endpoint(request: JobAnalyzeRequest):
    try:
        return analyze_job(request.job_text)
    except LLMError as exc:
        raise _handle_llm_error(exc) from exc


@app.post("/generate-answers")
def generate_answers_endpoint(request: AnswerRequest):
    try:
        result = generate_answers(
            job_text=request.job_text,
            questions=request.questions,
            response_language=request.response_language,
        )
        return {"result": result}
    except LLMError as exc:
        raise _handle_llm_error(exc) from exc


@app.post("/generate-cover-letter")
def generate_cover_letter_endpoint(request: CoverLetterRequest):
    try:
        result = generate_cover_letter(
            job_text=request.job_text,
            company=request.company,
            role=request.role,
            response_language=request.response_language,
        )
        return {"result": result}
    except LLMError as exc:
        raise _handle_llm_error(exc) from exc


@app.post("/analyze-and-save")
def analyze_and_save_endpoint(
    request: FullAnalysisRequest,
    db: Session = Depends(get_db),
):
    try:
        analysis = analyze_job(
            request.job_text,
            response_language=request.response_language,
        )
        cover_letter = generate_cover_letter(
            job_text=request.job_text,
            company=request.company,
            role=request.role,
            response_language=request.response_language,
        )
    except LLMError as exc:
        raise _handle_llm_error(exc) from exc

    application = None
    if request.save_application:
        application = Application(
            company=request.company or "Unknown",
            role=request.role or "Unknown",
            source=request.source,
            url=request.url,
            status="draft",
            fit_score=analysis.get("fit_score"),
            generated_pitch=analysis.get("pitch"),
            generated_cover_letter=cover_letter,
            raw_job_text=request.job_text,
            analysis_result=analysis.get("result"),
        )
        db.add(application)
        db.commit()
        db.refresh(application)

    return {
        "analysis": analysis,
        "cover_letter": cover_letter,
        "application": (
            ApplicationResponse.model_validate(application)
            if application
            else None
        ),
    }


@app.get("/applications", response_model=list[ApplicationResponse])
def list_applications(db: Session = Depends(get_db)):
    return db.query(Application).order_by(Application.id.desc()).all()


@app.get("/applications/ui", response_class=HTMLResponse)
def applications_ui():
    dashboard_path = PROJECT_ROOT / "ui" / "applications_dashboard.html"
    return dashboard_path.read_text(encoding="utf-8")


@app.post("/applications", response_model=ApplicationResponse)
def create_application(
    request: ApplicationCreate,
    db: Session = Depends(get_db),
):
    if request.status not in APPLICATION_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    application = Application(
        company=request.company,
        role=request.role,
        source=request.source,
        url=request.url,
        status=request.status,
        fit_score=request.fit_score,
        applied_at=utc_now_iso() if request.status == "applied" else None,
        notes=request.notes,
        generated_pitch=request.generated_pitch,
        generated_cover_letter=request.generated_cover_letter,
        raw_job_text=request.raw_job_text,
        analysis_result=request.analysis_result,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


@app.patch("/applications/{application_id}", response_model=ApplicationResponse)
def update_application(
    application_id: int,
    request: ApplicationUpdate,
    db: Session = Depends(get_db),
):
    application = db.get(Application, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    updates = request.model_dump(exclude_unset=True)
    if "status" in updates and updates["status"] not in APPLICATION_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    for field, value in updates.items():
        setattr(application, field, value)

    if updates.get("status") == "applied" and not application.applied_at:
        application.applied_at = utc_now_iso()

    db.commit()
    db.refresh(application)
    return application


@app.delete("/applications/{application_id}")
def delete_application(application_id: int, db: Session = Depends(get_db)):
    application = db.get(Application, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    db.delete(application)
    db.commit()
    return {"deleted": True}


@app.get("/learned-answers", response_model=list[LearnedAnswerResponse])
def list_learned_answers(db: Session = Depends(get_db)):
    return db.query(LearnedAnswer).order_by(LearnedAnswer.id.desc()).all()


@app.post("/learned-answers", response_model=LearnedAnswerResponse)
def create_learned_answer(
    request: LearnedAnswerCreate,
    db: Session = Depends(get_db),
):
    learned = LearnedAnswer(
        question_pattern=request.question_pattern,
        answer=request.answer,
        confidence=request.confidence,
        requires_confirmation=request.requires_confirmation,
    )
    db.add(learned)
    db.commit()
    db.refresh(learned)
    return learned


@app.post("/extension/analyze-page")
def extension_analyze_page(
    request: ExtensionAnalyzeRequest,
    db: Session = Depends(get_db),
):
    try:
        analysis = analyze_job(
            request.job_text,
            response_language=request.response_language,
        )
        cover_letter = ""
        if request.include_cover_letter:
            cover_letter = generate_cover_letter(
                job_text=request.job_text,
                company=request.company,
                role=request.role,
                response_language=request.response_language,
            )
    except LLMError as exc:
        raise _handle_llm_error(exc) from exc

    application = None
    if request.save_application:
        application = track_application(
            db,
            platform=request.platform,
            url=request.url,
            company=request.company,
            role=request.role or request.title,
            status="draft",
            job_text=request.job_text,
            fit_score=analysis.get("fit_score"),
            generated_pitch=analysis.get("pitch"),
            generated_cover_letter=cover_letter or None,
            analysis_result=analysis.get("result"),
        )

    return {
        "analysis": analysis,
        "cover_letter": cover_letter,
        "questions": get_analysis_questions(analysis.get("result", ""), db),
        "application": (
            ApplicationResponse.model_validate(application)
            if application
            else None
        ),
    }


@app.post("/extension/fill-form")
def extension_fill_form(
    request: ExtensionFillFormRequest,
    db: Session = Depends(get_db),
):
    try:
        field_dicts = [field.model_dump() for field in request.fields]
        logger.info(
            "fill-form: platform=%s url=%s fields=%d use_llm=%s",
            request.platform,
            request.url,
            len(field_dicts),
            request.use_llm,
        )
        for field in field_dicts[:8]:
            label = (field.get("label") or field.get("id") or "unknown")[:120]
            logger.info("  field: %s", label)
        mappings = map_form_fields(
            job_text=request.job_text,
            fields=field_dicts,
            db=db,
            use_llm=request.use_llm,
            response_language=request.response_language,
            platform=request.platform,
            company=request.company,
            role=request.role or request.title,
        )
    except LLMError as exc:
        raise _handle_llm_error(exc) from exc

    logger.info(
        "fill-form result: auto_fill=%d review=%d",
        sum(1 for item in mappings if item.get("fill")),
        sum(1 for item in mappings if item.get("answer") and not item.get("fill")),
    )

    return {
        "platform": request.platform,
        "url": request.url,
        "mappings": mappings,
        "auto_fill_count": sum(1 for item in mappings if item.get("fill")),
        "review_count": sum(
            1 for item in mappings if item.get("answer") and not item.get("fill")
        ),
        "pending_questions": mappings_need_user_input(mappings),
        "submit_allowed": False,
        "message": "Review filled fields and submit manually.",
    }


@app.get("/extension/missing-questions")
def extension_missing_questions(db: Session = Depends(get_db)):
    return {"questions": get_missing_profile_questions(db)}


@app.get("/extension/application-by-url")
def extension_application_by_url(
    url: str = Query(..., min_length=8),
    db: Session = Depends(get_db),
):
    application = (
        db.query(Application)
        .filter(Application.url == url)
        .order_by(Application.id.desc())
        .first()
    )
    if not application:
        return {"application": None}
    return {"application": ApplicationResponse.model_validate(application)}


@app.get("/extension/applications", response_model=list[ApplicationResponse])
def extension_list_applications(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return (
        db.query(Application)
        .order_by(Application.id.desc())
        .limit(limit)
        .all()
    )


@app.post("/extension/track-application", response_model=ApplicationResponse)
def extension_track_application(
    request: ExtensionTrackRequest,
    db: Session = Depends(get_db),
):
    if request.status not in APPLICATION_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    application = track_application(
        db,
        platform=request.platform,
        url=request.url,
        company=request.company or request.title,
        role=request.role or request.title,
        status=request.status,
        job_text=request.job_text,
        fit_score=request.fit_score,
        notes=request.notes,
    )
    logger.info(
        "track-application: id=%s status=%s url=%s",
        application.id,
        application.status,
        request.url,
    )
    return application


@app.post("/extension/save-answer", response_model=LearnedAnswerResponse)
def extension_save_answer(
    request: ExtensionSaveAnswerRequest,
    db: Session = Depends(get_db),
):
    learned = upsert_learned_answer(
        db,
        question_pattern=request.question_pattern,
        answer=request.answer,
        confidence=request.confidence,
        requires_confirmation=request.requires_confirmation,
    )
    return learned


@app.post("/generate-tailored-cv")
def generate_tailored_cv_endpoint(request: TailoredCvRequest):
    try:
        result = generate_tailored_cv(
            job_text=request.job_text,
            company=request.company,
            role=request.role,
            response_language=request.response_language,
        )
        return {"result": result}
    except LLMError as exc:
        raise _handle_llm_error(exc) from exc


@app.post("/extension/generate-cv")
def extension_generate_cv(request: ExtensionGenerateCvRequest):
    try:
        cv_text = generate_tailored_cv(
            job_text=request.job_text,
            company=request.company,
            role=request.role or request.title,
            response_language=request.response_language,
            platform=request.platform,
        )
    except LLMError as exc:
        raise _handle_llm_error(exc) from exc

    return {
        "cv": cv_text,
        "platform": request.platform,
        "url": request.url,
        "response_language": request.response_language,
    }

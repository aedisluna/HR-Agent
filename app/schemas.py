from typing import Literal, Optional

from pydantic import BaseModel, Field

ResponseLanguage = Literal["auto", "ru", "en"]


class JobAnalyzeRequest(BaseModel):
    job_text: str = Field(..., min_length=20)


class AnswerRequest(BaseModel):
    job_text: str = Field(..., min_length=20)
    questions: list[str] = Field(..., min_length=1)
    response_language: ResponseLanguage = "auto"


class CoverLetterRequest(BaseModel):
    job_text: str = Field(..., min_length=20)
    company: Optional[str] = None
    role: Optional[str] = None
    response_language: ResponseLanguage = "auto"


class TailoredCvRequest(BaseModel):
    job_text: str = Field(..., min_length=20)
    company: Optional[str] = None
    role: Optional[str] = None
    response_language: ResponseLanguage = "auto"


class ApplicationCreate(BaseModel):
    company: str
    role: str
    source: str = "manual"
    url: Optional[str] = None
    status: str = "draft"
    fit_score: Optional[int] = Field(default=None, ge=0, le=100)
    notes: Optional[str] = None
    generated_pitch: Optional[str] = None
    generated_cover_letter: Optional[str] = None
    raw_job_text: Optional[str] = None
    analysis_result: Optional[str] = None


class ApplicationUpdate(BaseModel):
    company: Optional[str] = None
    role: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None
    status: Optional[str] = None
    fit_score: Optional[int] = Field(default=None, ge=0, le=100)
    notes: Optional[str] = None
    generated_pitch: Optional[str] = None
    generated_cover_letter: Optional[str] = None
    raw_job_text: Optional[str] = None
    analysis_result: Optional[str] = None


class ApplicationResponse(BaseModel):
    id: int
    company: str
    role: str
    source: str
    url: Optional[str]
    status: str
    fit_score: Optional[int]
    applied_at: Optional[str]
    notes: Optional[str]
    generated_pitch: Optional[str]
    generated_cover_letter: Optional[str]
    raw_job_text: Optional[str]
    analysis_result: Optional[str]

    model_config = {"from_attributes": True}


class LearnedAnswerCreate(BaseModel):
    question_pattern: str
    answer: str
    confidence: str = "medium"
    requires_confirmation: bool = True


class LearnedAnswerResponse(BaseModel):
    id: int
    question_pattern: str
    answer: str
    confidence: str
    requires_confirmation: bool

    model_config = {"from_attributes": True}


class FullAnalysisRequest(BaseModel):
    job_text: str = Field(..., min_length=20)
    company: Optional[str] = None
    role: Optional[str] = None
    source: str = "manual"
    url: Optional[str] = None
    save_application: bool = True
    response_language: ResponseLanguage = "auto"


class FormField(BaseModel):
    id: str
    label: str
    field_type: str = "text"
    name: Optional[str] = None
    placeholder: Optional[str] = None
    required: bool = False


class ExtensionFillFormRequest(BaseModel):
    job_text: str = Field(..., min_length=10)
    platform: str
    url: str
    title: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    fields: list[FormField] = Field(..., min_length=1)
    use_llm: bool = True
    response_language: ResponseLanguage = "auto"


class ExtensionAnalyzeRequest(BaseModel):
    platform: str
    url: str
    title: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    job_text: str = Field(..., min_length=10)
    save_application: bool = True
    include_cover_letter: bool = False
    response_language: ResponseLanguage = "auto"


class ExtensionGenerateCvRequest(BaseModel):
    platform: str
    url: str
    title: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    job_text: str = Field(..., min_length=10)
    response_language: ResponseLanguage = "auto"
    save_application: bool = False


class ExtensionSaveAnswerRequest(BaseModel):
    question_pattern: str = Field(..., min_length=3)
    answer: str = Field(..., min_length=1)
    confidence: str = "high"
    requires_confirmation: bool = False
    fill_field_id: Optional[str] = None


class ExtensionTrackRequest(BaseModel):
    platform: str
    url: str
    title: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    job_text: Optional[str] = None
    status: str = "draft"
    fit_score: Optional[int] = Field(default=None, ge=0, le=100)
    notes: Optional[str] = None

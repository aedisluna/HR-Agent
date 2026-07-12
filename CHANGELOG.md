# Changelog

All notable changes to HR Agent are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
The project currently uses semantic version numbers for application releases.

## [Unreleased]

## [0.6.2] - 2026-07-12

### Added

- Windows local bridge installer for starting the launcher from the Chrome
  extension. After one double-click installation, **Start backend** no longer
  requires a terminal command or an open console window.
- Personal skill labels and aliases now live in a gitignored YAML catalog rather
  than application source code.
- Generic ATS extraction and review-only form filling now support accessible
  same-origin iframes and richer field-label recovery.
- Offline pytest API, ATS, memory-import, native-host, and quality regression
  coverage with a 60% branch-coverage gate.

### Changed

- Vacancy analysis now receives a prioritized resume, project, and skills-inventory
  context, while tailored CV retrieval excludes current-project detail blocks.
- Browser extension and backend versions are aligned at 0.6.2.

### Fixed

- Generic ATS form matching now resolves profile identity fields before asking the
  model and leaves unknown or confirmation-required answers for manual review.
- The native launcher bridge now selects Python 3.11 instead of the Windows default
  "py -3" interpreter when no project virtual environment exists.

### Validation

- 38 offline tests pass with 61.2% branch coverage; the suite uses isolated SQLite
  databases and mocked LLM boundaries for deterministic assertions.

## [0.6.1] - 2026-07-11

### Fixed

- Every must-have requirement must now be classified as `matched`, `missing`, or
  `unknown` with an explanation.
- Matched requirements must reference concrete candidate-fact evidence.
- Matching and missing sections are derived from requirement assessments instead of
  trusting independent optional arrays from the model.
- Contradictory results such as a high fit score with no confirmed matches are
  rejected and regenerated once with validation feedback.
- Empty UI sections now use explicit messages instead of the ambiguous `None`.

### Validation

- Added regression coverage for derived requirement sections and automatic repair of
  inconsistent structured analysis.

## [0.6.0] - 2026-07-10

### Added

- Structured vacancy analysis backed by a validated Pydantic JSON schema.
- SQLite candidate memory with individually addressable, confirmed profile facts.
- Versioned `job_analyses` records linked to applications and vacancy content hashes.
- Versioned `generated_artifacts` records for tailored CVs and cover letters.
- Automatic CV quality checks for:
  - platform-specific length and formatting;
  - required LinkedIn resume sections;
  - coverage of confirmed vacancy keywords;
  - vacancy keywords used without support in confirmed candidate facts.
- Ollama run telemetry, including prompt/output token counts, generation durations,
  model name, task name, status, and errors.
- `GET /metrics` endpoint with aggregate model reliability, latency, and artifact
  quality statistics.
- Vacancy-memory and quality indicators in the browser extension after CV generation.
- Unit tests for structured analysis, candidate-fact retrieval, analysis/artifact
  persistence, CV memory injection, and deterministic quality checks.

### Changed

- Vacancy analysis now uses Ollama structured outputs instead of parsing free-form
  Markdown with regular expressions.
- Candidate context is retrieved by relevance from SQLite rather than sending the
  complete profile, resume, and interview-story collection on every model call.
- CV generation reuses the saved analysis for the same application URL and vacancy
  text, including form-generated cover letters.
- Vacancy content hashes prevent stale analyses from being reused after a job
  description changes.
- Prompt sizes are bounded by retrieving only relevant confirmed facts and a limited
  set of facts requiring confirmation.
- Generated CVs and cover letters are automatically evaluated and stored together
  with their model and prompt versions.
- Application deletion also removes its linked analyses and generated artifacts.
- Application version increased from 0.5.3 to 0.6.0.
- README architecture and usage documentation now cover memory and quality metrics.

### Fixed

- Chrome extension API compatibility now targets backend 0.6.x, and the extension
  manifest version matches the backend application version.
- Re-importing profile data no longer deletes answers learned through the browser
  extension.
- Profile import now adds only missing standard-answer patterns.
- Candidate facts are refreshed independently from learned application answers.
- Long profile prompts no longer risk consuming the full 8192-token context window
  before the vacancy and output instructions are processed.
- Local runtime output under `output/` is excluded from version control.

### Validation

- Added six automated unit tests.
- Verified all Python files parse successfully.
- Verified all browser-extension JavaScript files with Node syntax checks.
- Verified structured analysis against the configured local Ollama model.
- Verified backend health and metrics endpoints on version 0.6.0.

## [0.5.3] - 2026-07-08

### Existing baseline

- Local Ollama-backed vacancy analysis and tailored document generation.
- FastAPI backend, Chrome extension, SQLite application tracking, learned answers,
  and HH.ru, LinkedIn, and generic ATS support.

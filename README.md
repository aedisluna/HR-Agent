# HR Agent

Local AI assistant for job search: analyze vacancies, generate tailored CVs and cover letters, fill application forms, and track applications — powered by **Ollama** (local LLM), **FastAPI**, and a **Chrome extension**.

Works with **LinkedIn**, **HH.ru**, and generic ATS pages. Everything runs on your machine; no cloud API keys required.

## Features

- **Fit score & analysis** — compare a vacancy against your profile with conservative scoring rules
- **Tailored CV / cover letter** — platform-specific prompts (HH.ru, LinkedIn, generic)
- **Form fill assist** — maps form fields to your standard answers (manual submit only)
- **Application CRM** — SQLite tracker + web dashboard
- **Vacancy memory** — structured analyses are reused when writing a CV
- **Quality metrics** — saved artifacts, format/grounding checks, and Ollama telemetry
- **Chrome side panel** — analyze, generate, fill, notes, status on the job page

## Architecture

```
Job page → Chrome extension → FastAPI workflow → Ollama
                                  ↓
                    SQLite (applications + memory)
                       ├─ candidate_facts
                       ├─ job_analyses
                       ├─ generated_artifacts
                       ├─ learned_answers
                       └─ llm_runs
```

The workflow is deliberately controlled rather than autonomous: analyze the vacancy,
retrieve confirmed evidence, generate the document, run deterministic checks, and
store the result. The model never receives unrestricted database access.

Launcher service on port **17890** starts/stops the backend from the extension.

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com/) with a local model (default: `llama3.1-8b-q8-local`)
- Google Chrome (for the extension)

## Setup

### 1. Clone and install Python dependencies

```bash
git clone https://github.com/aedisluna/HR-Agent.git
cd HR-Agent
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
```

### 2. Pull the Ollama model

```bash
ollama pull llama3.1-8b-q8-local
```

Edit `app/config.py` if you use a different model name.

### 3. Create your profile data

Personal files in `data/` are **not** in git. Copy templates:

```bash
python scripts/setup_profile_data.py
```

Then edit `data/candidate_profile.yaml`, `data/resume.md`, `data/standard_answers.yaml`, etc.
See [data/README.md](data/README.md) for details.

### 4. Start the backend

**Option A — launcher (recommended for extension):**

```bash
python scripts/launcher.py
```

**Option B — direct:**

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Verify: http://127.0.0.1:8001/health

### 5. Load the Chrome extension

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. **Load unpacked** → select the `extension/` folder
4. Open a job page on LinkedIn or HH.ru — the HR Agent panel appears on the right

### 6. Seed learned answers (optional)

On first backend start, standard answers and confirmed candidate facts are imported
into SQLite automatically. To refresh file-backed memory after editing YAML or the
base resume:

```bash
curl -X POST http://127.0.0.1:8001/import-profile
```

The refresh replaces file-backed `candidate_facts` and adds missing standard-answer
patterns. Answers learned through the extension are preserved.

## Usage

1. Open a vacancy on LinkedIn or HH.ru
2. Click **Analyze** to create and save a structured vacancy analysis
3. Review fit score, gaps, risks, and the suggested pitch
4. Click **CV** — the generator reuses that exact analysis and retrieves relevant
   confirmed candidate facts from SQLite
5. Review the displayed quality score and generated text
6. Use **Fill** for application fields and cover letters
7. Submit manually, then track status and notes in the job card

Applications dashboard: http://127.0.0.1:8001/applications/ui

## Project structure

```
app/
  main.py             FastAPI endpoints and workflow orchestration
  analysis_models.py  validated structured vacancy schema
  memory.py           candidate-fact retrieval and artifact persistence
  quality.py          deterministic CV quality checks
  storage.py          SQLite models and sessions
extension/            Chrome content scripts and side panel
prompts/              model system prompts
data/                 local profile and SQLite DB (real data is gitignored)
scripts/              launcher, smoke test, profile setup
tests/                offline unit tests for memory, quality, and generation
ui/                   applications dashboard (HTML / Streamlit)
CHANGELOG.md           release history
```

## Configuration

| Setting | File | Default |
|---------|------|---------|
| Ollama model | `app/config.py` | `llama3.1-8b-q8-local` |
| Backend port | `app/main.py` / launcher | `8001` |
| Launcher port | `scripts/launcher.py` | `17890` |

## Vacancy memory workflow

1. **Analyze** asks Ollama for validated JSON: score, recommendation, requirements,
   matches, gaps, risks, ATS keywords, strategy, pitch, and candidate questions.
2. The analysis is stored in `job_analyses` with the application ID, URL, vacancy
   content hash, model, and prompt version.
3. **CV** or **Fill** locates the analysis for the same URL and content hash.
4. `memory.py` ranks confirmed `candidate_facts` against the vacancy and analysis,
   then builds a bounded context instead of sending the entire profile.
5. The generated document is checked and stored in `generated_artifacts`.

If the vacancy text changes, its hash changes and the old structured analysis is not
reused. Existing pre-0.6.0 Markdown analyses can still be used when the stored vacancy
text matches.

### SQLite data

| Table | Purpose |
|-------|---------|
| `applications` | vacancy CRM, status, notes, raw job text |
| `candidate_facts` | confirmed profile/resume facts available for retrieval |
| `job_analyses` | versioned structured vacancy analyses |
| `generated_artifacts` | CVs and letters with model, prompt, and quality metadata |
| `learned_answers` | reusable answers for application forms |
| `llm_runs` | Ollama task, tokens, durations, status, and errors |

New tables are created automatically when the backend starts. The local database
remains `data/applications.db` and is excluded from git.

## Quality and telemetry

Each generated document receives deterministic checks for:

- platform length and formatting constraints;
- required LinkedIn resume sections;
- coverage of vacancy keywords confirmed by candidate facts;
- vacancy keywords used in the document without supporting profile evidence.

The extension displays the score after generation. Full aggregate metrics are
available at http://127.0.0.1:8001/metrics:

- successful and failed LLM runs;
- average Ollama duration;
- generated/evaluated artifact count;
- quality pass rate and average score.

These checks are guardrails, not a guarantee that a CV is correct. Always review the
generated document before submitting it.

## Useful endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | backend version and availability |
| `POST /extension/analyze-page` | analyze and optionally save a vacancy |
| `POST /extension/generate-cv` | reuse vacancy memory and create an evaluated artifact |
| `POST /extension/fill-form` | map learned/model answers to detected fields |
| `POST /import-profile` | refresh candidate facts and add missing answer patterns |
| `GET /applications/ui` | local application dashboard |
| `GET /metrics` | model and artifact quality aggregates |
| `GET /debug/logs` | recent local backend and launcher logs |

## Testing

Offline unit tests do not require Ollama or a running backend:

```bash
python -m unittest discover -s tests -v
```

For an end-to-end check, start the backend and Ollama, then run:

```bash
python scripts/smoke_test.py
```

The smoke test exercises the live API and upserts a fixed smoke-test vacancy into
the local database.

## Privacy & security

- Profile data stays in `data/` on your machine (gitignored)
- Backend binds to `127.0.0.1` only — any local process can call the API; do not expose port 8001
- Launcher control endpoints require the `X-HR-Agent-Client: extension` header (browser extension only)
- `/profile` and `/debug/logs` return local profile and log data — localhost use only
- No external LLM API keys — Ollama runs locally
- Do **not** commit real profile files; use `*.example.*` templates

See [docs/GITHUB_PUBLISHING.md](docs/GITHUB_PUBLISHING.md) if the repo was previously pushed with personal data in git history.

## Platform disclaimer

This tool assists with reading job pages and filling forms. **You** submit applications manually.
Automating clicks or submissions on LinkedIn, HH.ru, or ATS platforms may violate their Terms of Service.
Use at your own risk.

## License

MIT — see [LICENSE](LICENSE).

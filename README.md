# HR Agent

Local AI assistant for job search: analyze vacancies, generate tailored CVs and cover letters, fill application forms, and track applications — powered by **Ollama** (local LLM), **FastAPI**, and a **Chrome extension**.

Works with **LinkedIn**, **HH.ru**, and generic ATS pages. Everything runs on your machine; no cloud API keys required.

## Features

- **Fit score & analysis** — compare a vacancy against your profile with conservative scoring rules
- **Tailored CV / cover letter** — platform-specific prompts (HH.ru, LinkedIn, generic)
- **Form fill assist** — maps form fields to your standard answers (manual submit only)
- **Application CRM** — SQLite tracker + web dashboard
- **Chrome side panel** — analyze, generate, fill, notes, status on the job page

## Architecture

```
Chrome extension  →  FastAPI (port 8001)  →  Ollama (port 11434)
        ↓                    ↓
   content scripts      SQLite (applications.db)
```

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

On first backend start, standard answers are imported into SQLite automatically.
To re-import after editing YAML files:

```bash
curl -X POST http://127.0.0.1:8001/import-profile
```

## Usage

1. Open a vacancy on LinkedIn or HH.ru
2. Click **Analyze** in the side panel
3. Review fit score, gaps, and suggested pitch
4. **Generate CV** or **Fill** form fields (always review before submitting)
5. Track status and notes in the job card

Applications dashboard: http://127.0.0.1:8001/applications/ui

## Project structure

```
app/           FastAPI backend, LLM calls, analyzers
extension/     Chrome extension (content scripts + side panel)
prompts/       LLM system prompts
data/          Your profile (local only; *.example.* templates in repo)
scripts/       launcher, smoke test, profile setup
ui/            Applications dashboard (HTML / Streamlit)
```

## Configuration

| Setting | File | Default |
|---------|------|---------|
| Ollama model | `app/config.py` | `llama3.1-8b-q8-local` |
| Backend port | `app/main.py` / launcher | `8001` |
| Launcher port | `scripts/launcher.py` | `17890` |

## Smoke test

With backend running:

```bash
python scripts/smoke_test.py
```

## Privacy & security

- Profile data stays in `data/` on your machine (gitignored)
- Backend binds to `127.0.0.1` only
- No external LLM API keys — Ollama runs locally
- Do **not** commit real profile files; use `*.example.*` templates

See [docs/GITHUB_PUBLISHING.md](docs/GITHUB_PUBLISHING.md) if the repo was previously pushed with personal data in git history.

## Platform disclaimer

This tool assists with reading job pages and filling forms. **You** submit applications manually.
Automating clicks or submissions on LinkedIn, HH.ru, or ATS platforms may violate their Terms of Service.
Use at your own risk.

## License

MIT — see [LICENSE](LICENSE).

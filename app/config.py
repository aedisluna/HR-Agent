from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROMPTS_DIR = PROJECT_ROOT / "prompts"

APP_VERSION = "0.6.0"

OLLAMA_URL = "http://localhost:11434/api/chat"

# Speed vs quality (RTX 5060 Ti 16GB):
# - llama3.1-8b-local      ~5 GB Q4 — fastest, weaker Russian grammar
# - phi3-local             ~2.4 GB   — fastest, weaker Russian
# - llama3.1-8b-q8-local   ~8.5 GB Q8 — best Russian quality (recommended)
MODEL = "llama3.1-8b-q8-local"
MODEL_FAST = MODEL
MODEL_CV = MODEL

OLLAMA_NUM_CTX = 8192
OLLAMA_NUM_PREDICT = 2048
OLLAMA_KEEP_ALIVE = "30m"
JOB_TEXT_MAX_CHARS = 6000

APPLICATION_STATUSES = [
    "draft",
    "applied",
    "waiting",
    "recruiter_screen",
    "test_task",
    "interview",
    "rejected",
    "offer",
]

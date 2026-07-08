"""Quick smoke tests for the HR Agent API."""

from __future__ import annotations

import sys

import requests

from app.config import APP_VERSION

BASE = "http://127.0.0.1:8001"
SMOKE_JOB_TEXT = (
    "QA Engineer with API testing, SQL, and integration testing experience "
    "required for a fintech project."
)


def check(name: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")
    if not ok:
        raise SystemExit(1)


def ollama_available() -> bool:
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False


def main() -> None:
    health = requests.get(f"{BASE}/health", timeout=5).json()
    check("health", health.get("status") == "ok", str(health))
    check(
        "api version",
        health.get("version", "").split(".")[:2] == APP_VERSION.split(".")[:2],
        health.get("version"),
    )

    ui = requests.get(f"{BASE}/applications/ui", timeout=5)
    check("applications ui", ui.status_code == 200 and "<table>" in ui.text.lower())

    track = requests.post(
        f"{BASE}/extension/track-application",
        json={
            "platform": "hh",
            "url": "https://hh.ru/vacancy/smoke-test",
            "company": "Smoke Co",
            "role": "QA Engineer",
            "status": "draft",
            "job_text": SMOKE_JOB_TEXT,
        },
        timeout=5,
    )
    check("track application", track.status_code == 200, track.text[:120])

    track2 = requests.post(
        f"{BASE}/extension/track-application",
        json={
            "platform": "hh",
            "url": "https://hh.ru/vacancy/smoke-test",
            "company": "Smoke Co",
            "role": "QA Engineer",
            "status": "draft",
            "fit_score": 77,
        },
        timeout=5,
    )
    data2 = track2.json()
    check(
        "track upsert",
        track2.status_code == 200 and data2.get("fit_score") == 77,
        f"id={data2.get('id')}",
    )

    fill = requests.post(
        f"{BASE}/extension/fill-form",
        json={
            "platform": "hh",
            "url": "https://hh.ru/vacancy/smoke-test",
            "job_text": SMOKE_JOB_TEXT,
            "use_llm": False,
            "fields": [
                {
                    "id": "1",
                    "label": "Планируете работать на территории России?",
                    "field_type": "textarea",
                    "name": "task_1",
                    "placeholder": "Писать тут",
                    "required": True,
                }
            ],
        },
        timeout=10,
    )
    fill_data = fill.json()
    check(
        "fill form",
        fill.status_code == 200 and fill_data.get("auto_fill_count", 0) >= 1,
        str(fill_data.get("auto_fill_count")),
    )

    analyze_save = requests.post(
        f"{BASE}/analyze-and-save",
        json={
            "job_text": SMOKE_JOB_TEXT,
            "company": "Smoke Co",
            "role": "QA Engineer",
            "save_application": False,
        },
        timeout=120 if ollama_available() else 5,
    )
    if ollama_available():
        check(
            "analyze and save",
            analyze_save.status_code == 200
            and "analysis" in analyze_save.json(),
            analyze_save.text[:120],
        )
    else:
        check(
            "analyze and save",
            analyze_save.status_code in {503, 500},
            "skipped LLM body check (Ollama offline)",
        )

    if ollama_available():
        cv = requests.post(
            f"{BASE}/extension/generate-cv",
            json={
                "platform": "hh",
                "url": "https://hh.ru/vacancy/smoke-test",
                "company": "Smoke Co",
                "role": "QA Engineer",
                "job_text": SMOKE_JOB_TEXT,
            },
            timeout=120,
        )
        check("generate cv", cv.status_code == 200 and len(cv.json().get("cv", "")) > 100)
    else:
        print("[SKIP] generate cv — Ollama offline")

    print("All smoke tests passed.")


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as exc:
        print(f"[FAIL] API unreachable: {exc}")
        sys.exit(1)

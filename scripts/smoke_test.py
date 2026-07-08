"""Quick smoke tests for the HR Agent API."""

from __future__ import annotations

import sys

import requests

BASE = "http://127.0.0.1:8001"


def check(name: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")
    if not ok:
        raise SystemExit(1)


def main() -> None:
    health = requests.get(f"{BASE}/health", timeout=5).json()
    check("health", health.get("status") == "ok", str(health))

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
            "job_text": "QA engineer smoke test vacancy description",
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
            "job_text": "QA engineer with API testing experience",
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

    cv = requests.post(
        f"{BASE}/extension/generate-cv",
        json={
            "platform": "hh",
            "url": "https://hh.ru/vacancy/smoke-test",
            "company": "Smoke Co",
            "role": "QA Engineer",
            "job_text": "QA engineer with API testing and automation experience",
        },
        timeout=120,
    )
    check("generate cv", cv.status_code == 200 and len(cv.json().get("cv", "")) > 100)

    print("All smoke tests passed.")


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as exc:
        print(f"[FAIL] API unreachable: {exc}")
        sys.exit(1)

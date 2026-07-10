import json
import logging
from typing import Any

import requests

from app.config import (
    MODEL,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_NUM_CTX,
    OLLAMA_NUM_PREDICT,
    OLLAMA_URL,
)

logger = logging.getLogger("hr_agent.llm")


class LLMError(Exception):
    pass


def _record_llm_run(
    *,
    task: str,
    model: str,
    status: str,
    prompt_chars: int,
    data: dict[str, Any] | None = None,
    output_chars: int | None = None,
    error: str | None = None,
) -> None:
    """Persist Ollama telemetry without making generation depend on metrics storage."""

    try:
        from app.storage import LLMRun, SessionLocal, init_db, utc_now_iso

        init_db()
        db = SessionLocal()
        try:
            payload = data or {}
            db.add(
                LLMRun(
                    task=task,
                    model=model,
                    status=status,
                    prompt_chars=prompt_chars,
                    output_chars=output_chars,
                    prompt_tokens=payload.get("prompt_eval_count"),
                    output_tokens=payload.get("eval_count"),
                    total_duration_ns=payload.get("total_duration"),
                    load_duration_ns=payload.get("load_duration"),
                    prompt_eval_duration_ns=payload.get("prompt_eval_duration"),
                    eval_duration_ns=payload.get("eval_duration"),
                    error=error,
                    created_at=utc_now_iso(),
                )
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        logger.exception("Could not persist LLM telemetry")


def ask_llm(
    system_prompt: str,
    user_prompt: str,
    timeout: int = 180,
    *,
    model: str | None = None,
    num_ctx: int | None = None,
    num_predict: int | None = None,
    response_schema: Any | None = None,
    temperature: float | None = None,
    task: str = "generic",
) -> str:
    selected_model = model or MODEL
    prompt_chars = len(system_prompt) + len(user_prompt)
    payload: dict[str, Any] = {
        "model": selected_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": {
            "num_ctx": num_ctx or OLLAMA_NUM_CTX,
            "num_predict": num_predict or OLLAMA_NUM_PREDICT,
        },
    }
    if temperature is not None:
        payload["options"]["temperature"] = temperature
    if response_schema is not None:
        schema = (
            response_schema.model_json_schema()
            if hasattr(response_schema, "model_json_schema")
            else response_schema
        )
        payload["format"] = schema

    logger.info(
        "LLM request: task=%s, model=%s, system_chars=%d, user_chars=%d, num_ctx=%s",
        task,
        selected_model,
        len(system_prompt),
        len(user_prompt),
        payload["options"]["num_ctx"],
    )

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except requests.ConnectionError as exc:
        message = "Cannot connect to Ollama. Start it with: ollama serve"
        logger.error("Ollama connection failed")
        _record_llm_run(
            task=task, model=selected_model, status="error",
            prompt_chars=prompt_chars, error=message,
        )
        raise LLMError(message) from exc
    except requests.Timeout as exc:
        message = "Ollama request timed out. Try a smaller model."
        logger.error("Ollama request timed out after %ss", timeout)
        _record_llm_run(
            task=task, model=selected_model, status="error",
            prompt_chars=prompt_chars, error=message,
        )
        raise LLMError(message) from exc
    except requests.HTTPError as exc:
        message = f"Ollama request failed: {exc}"
        logger.error("Ollama HTTP error: %s", exc)
        _record_llm_run(
            task=task, model=selected_model, status="error",
            prompt_chars=prompt_chars, error=message,
        )
        raise LLMError(message) from exc
    except requests.RequestException as exc:
        message = f"Ollama request failed: {exc}"
        logger.error("Ollama request failed: %s", exc)
        _record_llm_run(
            task=task, model=selected_model, status="error",
            prompt_chars=prompt_chars, error=message,
        )
        raise LLMError(message) from exc
    except json.JSONDecodeError as exc:
        message = "Ollama returned an invalid response."
        logger.error("Ollama returned invalid JSON")
        _record_llm_run(
            task=task, model=selected_model, status="error",
            prompt_chars=prompt_chars, error=message,
        )
        raise LLMError(message) from exc

    content = data.get("message", {}).get("content")
    if not content:
        message = "Ollama returned an empty response."
        logger.error("Ollama returned empty response")
        _record_llm_run(
            task=task, model=selected_model, status="error",
            prompt_chars=prompt_chars, data=data, error=message,
        )
        raise LLMError(message)

    content = content.strip()
    _record_llm_run(
        task=task,
        model=selected_model,
        status="ok",
        prompt_chars=prompt_chars,
        data=data,
        output_chars=len(content),
    )
    logger.info(
        "LLM response: task=%s, chars=%d, prompt_tokens=%s, output_tokens=%s",
        task,
        len(content),
        data.get("prompt_eval_count"),
        data.get("eval_count"),
    )
    return content

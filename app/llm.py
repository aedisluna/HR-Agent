import json
import logging

import requests

from app.config import (
    JOB_TEXT_MAX_CHARS,
    MODEL,
    MODEL_CV,
    MODEL_FAST,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_NUM_CTX,
    OLLAMA_NUM_PREDICT,
    OLLAMA_URL,
)

logger = logging.getLogger("hr_agent.llm")


class LLMError(Exception):
    pass


def ask_llm(
    system_prompt: str,
    user_prompt: str,
    timeout: int = 180,
    *,
    model: str | None = None,
    num_ctx: int | None = None,
    num_predict: int | None = None,
) -> str:
    selected_model = model or MODEL
    payload = {
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

    logger.info(
        "LLM request: model=%s, system_chars=%d, user_chars=%d, num_ctx=%s",
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
        logger.error("Ollama connection failed")
        raise LLMError(
            "Cannot connect to Ollama. Start it with: ollama serve"
        ) from exc
    except requests.Timeout as exc:
        logger.error("Ollama request timed out after %ss", timeout)
        raise LLMError("Ollama request timed out. Try a smaller model.") from exc
    except requests.HTTPError as exc:
        logger.error("Ollama HTTP error: %s", exc)
        raise LLMError(f"Ollama request failed: {exc}") from exc
    except requests.RequestException as exc:
        logger.error("Ollama request failed: %s", exc)
        raise LLMError(f"Ollama request failed: {exc}") from exc
    except json.JSONDecodeError as exc:
        logger.error("Ollama returned invalid JSON")
        raise LLMError("Ollama returned an invalid response.") from exc

    content = data.get("message", {}).get("content")
    if not content:
        logger.error("Ollama returned empty response")
        raise LLMError("Ollama returned an empty response.")
    logger.info("LLM response: chars=%d", len(content))
    return content.strip()

import re

SUPPORTED_LANGUAGES = ("auto", "ru", "en")


def detect_language(text: str) -> str:
    cyrillic = len(re.findall(r"[А-Яа-яЁё]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if cyrillic > latin and cyrillic >= 20:
        return "ru"
    if latin >= 20:
        return "en"
    return "en"


def resolve_language(job_text: str, requested: str = "auto") -> str:
    if requested in ("ru", "en"):
        return requested
    return detect_language(job_text)


def language_instruction(language: str) -> str:
    if language == "ru":
        return "Write all output in Russian."
    return "Write all output in English."

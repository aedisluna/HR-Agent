"""Central logging setup and log file readers."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import PROJECT_ROOT

LOGS_DIR = PROJECT_ROOT / "logs"
BACKEND_LOG = LOGS_DIR / "hr-agent.log"
LAUNCHER_LOG = LOGS_DIR / "launcher.log"

_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_CONFIGURED = False


def setup_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    file_handler = RotatingFileHandler(
        BACKEND_LOG,
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.WARNING)

    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    _CONFIGURED = True


def read_log_tail(path: Path, lines: int = 200) -> list[str]:
    if not path.exists():
        return []

    safe_lines = max(1, min(lines, 1000))
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        content = handle.readlines()

    return [line.rstrip("\n") for line in content[-safe_lines:]]


def append_launcher_log(message: str) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    from datetime import datetime

    timestamp = datetime.now().strftime(_DATE_FORMAT)
    with LAUNCHER_LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} | INFO | launcher | {message}\n")


def clear_log_files(source: str = "all") -> dict[str, bool]:
    """Truncate backend and/or launcher log files."""
    if source not in {"all", "backend", "launcher"}:
        raise ValueError(f"Unsupported log source: {source}")

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    cleared = {"backend": False, "launcher": False}

    if source in {"all", "launcher"}:
        LAUNCHER_LOG.write_text("", encoding="utf-8")
        cleared["launcher"] = True

    if source in {"all", "backend"}:
        backend_cleared = False
        root = logging.getLogger()
        for handler in list(root.handlers):
            if not isinstance(handler, RotatingFileHandler):
                continue
            if Path(handler.baseFilename).resolve() != BACKEND_LOG.resolve():
                continue

            handler.acquire()
            try:
                if handler.stream:
                    handler.stream.close()
                handler.stream = handler._open()
                handler.stream.truncate(0)
                handler.flush()
                backend_cleared = True
            finally:
                handler.release()
            break

        if not backend_cleared:
            BACKEND_LOG.write_text("", encoding="utf-8")

        cleared["backend"] = True

    return cleared

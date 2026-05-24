from __future__ import annotations

import json
import logging
from typing import Any

SENSITIVE_KEYS = {"employee_name", "name", "email", "phone", "address"}


class JsonFormatter(logging.Formatter):
    """JSON formatter that redacts PII from structured log context.

    Callers pass context via a dict as the sole format argument:
        logger.info("event_name", {"key": "value"})
    This is an intentional alternative to extra= so the dict is redacted
    before emission and never leaks into log handlers.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "message": record.getMessage(),
            "name": record.name,
        }
        if isinstance(record.args, dict):
            payload["context"] = redact(record.args)
        return json.dumps(payload)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("***" if k.lower() in SENSITIVE_KEYS else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    return logger

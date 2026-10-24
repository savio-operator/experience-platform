"""Read only the configuration this foundation needs."""

import os


def get_log_level() -> str:
    level = os.environ.get("LOG_LEVEL", "INFO")
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise RuntimeError("Invalid LOG_LEVEL configuration")
    return level

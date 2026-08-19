"""Logging scaffold — one logger namespace for the whole suite.

Cloud Run captures stdout/stderr into Cloud Logging, so a plain stream handler
is enough in production; richer structured logging lands with the observability
work (roadmap Phase 3). Import with `from infra.log import get_logger`.
"""
from __future__ import annotations

import logging
import os

_CONFIGURED = False


def _configure() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    root = logging.getLogger("suite")
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S"))
        root.addHandler(handler)
    root.setLevel(os.getenv("SUITE_LOG_LEVEL", "INFO").upper())
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure()
    return logging.getLogger(f"suite.{name}")

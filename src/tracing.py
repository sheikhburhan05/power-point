"""LangSmith tracing configuration and helpers."""

from __future__ import annotations

import os
from typing import Any

from langsmith import traceable


def configure_tracing(
    *,
    enabled: bool | None = None,
    project: str | None = None,
) -> bool:
    """Enable LangSmith tracing via environment variables.

    Tracing is on when LANGSMITH_TRACING=true in .env or when ``enabled=True``
    is passed from the CLI (--trace flag).
    """
    if enabled is not None:
        os.environ["LANGSMITH_TRACING"] = "true" if enabled else "false"

    tracing_on = os.getenv("LANGSMITH_TRACING", "false").lower() in ("true", "1", "yes")
    if not tracing_on:
        return False

    if project:
        os.environ["LANGSMITH_PROJECT"] = project
    elif not os.getenv("LANGSMITH_PROJECT"):
        os.environ["LANGSMITH_PROJECT"] = "power-point-pipeline"

    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

    return bool(os.getenv("LANGSMITH_API_KEY"))


def tracing_status() -> dict[str, Any]:
    """Return current tracing config for CLI output."""
    enabled = os.getenv("LANGSMITH_TRACING", "false").lower() in ("true", "1", "yes")
    return {
        "enabled": enabled,
        "project": os.getenv("LANGSMITH_PROJECT", "power-point-pipeline"),
        "has_api_key": bool(os.getenv("LANGSMITH_API_KEY")),
        "endpoint": os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"),
    }


def trace_pipeline_step(name: str):
    """Decorator for non-LangChain pipeline steps (extract, apply, validate)."""
    return traceable(name=name, run_type="chain")

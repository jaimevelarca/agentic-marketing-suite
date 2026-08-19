"""Vertex AI Agent Engine (google-adk) wrapper for the product agents (ADR-04).

The Suite runs day-to-day as Cloud Run Jobs driving `BaseAgent.run` directly
(synchronous, cheap, easy to test). For agents we want on **Vertex AI Agent
Engine** — to get managed tracing, versioning, and sessions — this wraps a
`BaseAgent` as a google-adk `LlmAgent` whose single tool executes the agent's
deterministic `run()`. The model still does the generation inside `run()`; the
ADK layer adds Agent-Engine lifecycle around it.

`google-adk` is an OPTIONAL dependency (pyproject `[adk]` extra). Importing this
module never requires it; `to_adk_agent()` raises a clear error if it's missing.

Deploy (Vertex path — needs the Anthropic EULAs accepted in Vertex Model Garden):
    from agents.adk_wrapper import to_adk_agent
    from agents.layer1.agent_1_1 import AGENT
    root = to_adk_agent(AGENT)
    # adk deploy / vertexai Agent Engine create — see ../../LOADING.md (Option B)
"""
from __future__ import annotations

from typing import Any

from agents.base import BaseAgent


def to_adk_agent(agent: BaseAgent, *, name: str | None = None) -> Any:
    """Wrap a BaseAgent as an ADK LlmAgent exposing a `process_client` tool.

    Returns the constructed LlmAgent (type Any to avoid importing adk at module
    load). Raises ImportError with guidance if google-adk isn't installed.
    """
    try:
        from google.adk.agents import LlmAgent  # type: ignore
    except ImportError as e:  # pragma: no cover - optional dep
        raise ImportError(
            "google-adk is required for Agent Engine deploy. Install the extra: "
            "`pip install -e '.[adk]'`. For local/dev use BaseAgent.run directly."
        ) from e

    agent_name = name or f"agent_{agent.agent_id.replace('.', '_')}"

    def process_client(payload: dict) -> dict:
        """Run the agent's deterministic pipeline on one client payload and return
        the validated structured block (or the routing/error envelope)."""
        result = agent.run(payload)
        return {
            "agent_id": result.agent_id,
            "client_id": result.client_id,
            "valid": result.valid,
            "structured": result.structured,
            "error": result.error,
        }

    return LlmAgent(
        name=agent_name,
        model=agent.model,
        instruction=(
            f"You are agent {agent.agent_id} of the Digital Marketing AI Suite. "
            f"Call process_client with the incoming client payload and return its result. "
            f"Do not fabricate outputs — the tool performs the cached, schema-validated run."
        ),
        tools=[process_client],
    )

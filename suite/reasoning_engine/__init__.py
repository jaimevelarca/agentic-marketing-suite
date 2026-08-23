"""Marketing Suite Reasoning Engine package.

Vertex AI Reasoning Engine surface for Google Gemini Enterprise (Phase 7).
Allows conversational interaction, querying, and execution over the 19-agent
marketing intelligence pipeline.
"""
from suite.reasoning_engine.engine import MarketingSuiteReasoningEngine
from suite.reasoning_engine.tools import (
    get_client_summary,
    get_audience_and_competition,
    get_marketing_strategy,
    get_content_and_campaigns,
    get_creative_deliverables,
    get_run_execution_status,
)

__all__ = [
    "MarketingSuiteReasoningEngine",
    "get_client_summary",
    "get_audience_and_competition",
    "get_marketing_strategy",
    "get_content_and_campaigns",
    "get_creative_deliverables",
    "get_run_execution_status",
]

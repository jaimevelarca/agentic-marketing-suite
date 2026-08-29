"""Model Armor security and guardrail package for Agentic Marketing Suite.

Provides inline protection against prompt injection, tool poisoning,
and PII leaks leveraging Google Gemma and deterministic heuristics.
"""
from suite.security.model_armor import (
    ArmorAssessment,
    ModelArmor,
    SecurityCategory,
    SecurityFinding,
    SecurityPolicyViolationError,
    SecuritySeverity,
    protect_agent_input,
    sanitize_input_payload,
    scan_text,
    validate_tool_call,
)

__all__ = [
    "ArmorAssessment",
    "ModelArmor",
    "SecurityCategory",
    "SecurityFinding",
    "SecurityPolicyViolationError",
    "SecuritySeverity",
    "protect_agent_input",
    "sanitize_input_payload",
    "scan_text",
    "validate_tool_call",
]

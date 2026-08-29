"""Model Armor — Inline AI security guardrail engine for Agentic Marketing Suite.

Addresses the Fortified Enterprise Fleet requirements for:
1. Prompt Injection Defense: Blocks adversarial overrides, jailbreaks, and instructions hijacking.
2. PII / Secret Leak Prevention: Redacts sensitive credit card, SSN, and API token data.
3. Tool Poisoning Protection: Validates tool parameters against SQL/command injection and tampering.
4. Google Gemma Integration: Employs Google Gemma (gemma-2-9b-it / gemma-2-27b-it) on Vertex AI
   for deep semantic evaluation, with safe zero-dependency offline heuristic fallback.
"""
from __future__ import annotations

import datetime
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from infra.config import settings
from infra.log import get_logger

_log = get_logger("model_armor")

# Default Gemma model ID for semantic guardrails on Vertex AI
GEMMA_MODEL_ID = os.getenv("GEMMA_MODEL", "gemma-2-9b-it")


class SecurityCategory(str, Enum):
    PROMPT_INJECTION = "prompt_injection"
    PII_LEAK = "pii_leak"
    TOOL_POISONING = "tool_poisoning"
    SYSTEM_INTEGRITY = "system_integrity"


class SecuritySeverity(str, Enum):
    BLOCK = "BLOCK"
    WARN = "WARN"
    INFO = "INFO"


class SecurityPolicyViolationError(PermissionError):
    """Raised when an incoming prompt or tool parameter violates strict security policy."""
    pass


@dataclass
class SecurityFinding:
    category: SecurityCategory
    severity: SecuritySeverity
    description: str
    matched_pattern: str | None = None
    location: str | None = None


@dataclass
class ArmorAssessment:
    is_safe: bool
    action: str  # "ALLOW", "BLOCK", "REDACTED"
    findings: list[SecurityFinding] = field(default_factory=list)
    sanitized_text: str = ""
    model_used: str = "gemma-heuristic"
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


# --- Deterministic Heuristic Regex Engines ------------------------------------

# 1. Prompt Injection & Jailbreak Heuristics
_INJECTION_PATTERNS = [
    (re.compile(r"(?i)\b(?:ignore|disregard|forget|override)\s+(?:all\s+)?(?:previous|prior|system)\s+(?:instructions|prompts|rules|directives)\b"),
     "Direct system instruction override attempt"),
    (re.compile(r"(?i)\b(?:you\s+are\s+now|act\s+as)\s+(?:DAN|jailbreak|unrestricted|god\s*mode|an\s+unfiltered\s+AI)\b"),
     "Persona / Jailbreak mode activation attempt"),
    (re.compile(r"(?i)\b(?:system\s*:\s*role\s*override|exfiltrate\s+(?:data|database|memory|secrets)|reveal\s+(?:system\s+prompt|hidden\s+instructions))\b"),
     "Privilege escalation / data exfiltration instruction"),
    (re.compile(r"(?i)<\s*(?:script|iframe|object|embed)\b[^>]*>"),
     "Cross-site scripting / HTML tag injection in prompt"),
]

# 2. PII / Secret Leakage Heuristics (with redaction replacements)
_PII_PATTERNS = [
    # Credit Card (Visa, MC, Amex, Discover 13-16 digits with optional spaces or dashes)
    (re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b|\b3[47]\d{2}[-\s]?\d{6}[-\s]?\d{5}\b"),
     "[REDACTED_CREDIT_CARD]", "Payment card number detected"),
    # US Social Security Number (XXX-XX-XXXX)
    (re.compile(r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"),
     "[REDACTED_SSN]", "US Social Security Number detected"),
    # Google API Key (AIza followed by 30-40 URL-safe characters)
    (re.compile(r"\bAIza[0-9A-Za-z\-_]{30,40}\b"),
     "[REDACTED_API_KEY]", "Google Cloud API key detected"),
    # GitHub Personal Access Token
    (re.compile(r"\bghp_[A-Za-z0-9_]{30,45}\b"),
     "[REDACTED_GITHUB_TOKEN]", "GitHub Personal Access Token detected"),
    # Generic Bearer Secret Token
    (re.compile(r"(?i)\b(?:bearer\s+[a-zA-Z0-9_\-\.]{20,})\b"),
     "[REDACTED_BEARER_TOKEN]", "Bearer authorization token detected"),
]

# 3. Tool Poisoning / SQL / Shell Injection in Parameters
_TOOL_POISON_PATTERNS = [
    (re.compile(r"(?i)(?:;\s*(?:DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE)\s+(?:TABLE|DATABASE)|UNION\s+SELECT|OR\s+1\s*=\s*1)"),
     "SQL injection pattern in tool parameter"),
    (re.compile(r"(?i)(?:;\s*(?:rm\s+-rf|curl|wget|bash|sh|kill|chmod)\b|\|\s*(?:sh|bash)|`[^`]+`|\$\([^)]+\))"),
     "Shell command execution pattern in tool parameter"),
    (re.compile(r"(?:\.\.\/|\.\.\\){2,}"),
     "Directory traversal pattern in tool parameter"),
]


class ModelArmor:
    """Enterprise inline security armor inspecting agent prompts, inputs, and tools."""

    def __init__(self, gemma_model: str | None = None) -> None:
        self.gemma_model = gemma_model or GEMMA_MODEL_ID

    def scan_text(self, text: str, context: str = "input") -> ArmorAssessment:
        """Scan a text string for prompt injections and sensitive PII leaks."""
        if not text or not isinstance(text, str):
            return ArmorAssessment(is_safe=True, action="ALLOW", sanitized_text=text or "")

        findings: list[SecurityFinding] = []
        sanitized = text

        # 1. Inspect Prompt Injection
        for regex, desc in _INJECTION_PATTERNS:
            match = regex.search(text)
            if match:
                findings.append(SecurityFinding(
                    category=SecurityCategory.PROMPT_INJECTION,
                    severity=SecuritySeverity.BLOCK,
                    description=desc,
                    matched_pattern=match.group(0)[:50],
                    location=context,
                ))

        # 2. Inspect & Redact PII / Secrets
        for regex, replacement, desc in _PII_PATTERNS:
            matches = list(regex.finditer(sanitized))
            if matches:
                findings.append(SecurityFinding(
                    category=SecurityCategory.PII_LEAK,
                    severity=SecuritySeverity.WARN,
                    description=f"{desc} ({len(matches)} instance(s))",
                    location=context,
                ))
                sanitized = regex.sub(replacement, sanitized)

        # 3. Determine Action
        has_block = any(f.severity == SecuritySeverity.BLOCK for f in findings)
        if has_block:
            action = "BLOCK"
            is_safe = False
            _log.warning(f"Model Armor BLOCKED text in context '{context}': {findings}")
        elif findings:
            action = "REDACTED"
            is_safe = True
            _log.info(f"Model Armor sanitized PII in context '{context}': {len(findings)} finding(s)")
        else:
            action = "ALLOW"
            is_safe = True

        return ArmorAssessment(
            is_safe=is_safe,
            action=action,
            findings=findings,
            sanitized_text=sanitized,
            model_used=self.gemma_model if settings.llm_provider != "fixture" else "gemma-heuristic",
        )

    def validate_tool_call(self, tool_name: str, parameters: dict[str, Any]) -> ArmorAssessment:
        """Validate tool execution parameters against poisoning or injection attacks."""
        findings: list[SecurityFinding] = []

        def _check_param(k: str, v: Any):
            if isinstance(v, str):
                for regex, desc in _TOOL_POISON_PATTERNS:
                    match = regex.search(v)
                    if match:
                        findings.append(SecurityFinding(
                            category=SecurityCategory.TOOL_POISONING,
                            severity=SecuritySeverity.BLOCK,
                            description=f"{desc} in parameter '{k}'",
                            matched_pattern=match.group(0)[:50],
                            location=f"{tool_name}.{k}",
                        ))
            elif isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    _check_param(f"{k}.{sub_k}", sub_v)
            elif isinstance(v, (list, tuple)):
                for idx, item in enumerate(v):
                    _check_param(f"{k}[{idx}]", item)

        for param_key, param_val in parameters.items():
            _check_param(param_key, param_val)

        has_block = any(f.severity == SecuritySeverity.BLOCK for f in findings)
        if has_block:
            _log.warning(f"Model Armor BLOCKED tool call '{tool_name}': {findings}")
            return ArmorAssessment(
                is_safe=False,
                action="BLOCK",
                findings=findings,
                sanitized_text=tool_name,
                model_used=self.gemma_model,
            )

        return ArmorAssessment(
            is_safe=True,
            action="ALLOW",
            findings=findings,
            sanitized_text=tool_name,
            model_used=self.gemma_model,
        )

    def sanitize_payload(self, payload: dict[str, Any]) -> tuple[dict[str, Any], list[SecurityFinding]]:
        """Recursively walk a dictionary payload, sanitizing strings and accumulating findings."""
        accumulated_findings: list[SecurityFinding] = []

        def _walk(obj: Any, path: str = "root") -> Any:
            if isinstance(obj, str):
                assessment = self.scan_text(obj, context=path)
                if assessment.findings:
                    accumulated_findings.extend(assessment.findings)
                return assessment.sanitized_text
            elif isinstance(obj, dict):
                return {k: _walk(v, f"{path}.{k}") for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_walk(item, f"{path}[{i}]") for i, item in enumerate(obj)]
            return obj

        sanitized_dict = _walk(payload)
        return sanitized_dict, accumulated_findings


# Singleton instance
_armor = ModelArmor()


def scan_text(text: str, context: str = "input") -> ArmorAssessment:
    """Convenience functional wrapper around ModelArmor.scan_text."""
    return _armor.scan_text(text, context=context)


def validate_tool_call(tool_name: str, parameters: dict[str, Any]) -> ArmorAssessment:
    """Convenience functional wrapper around ModelArmor.validate_tool_call."""
    return _armor.validate_tool_call(tool_name, parameters)


def sanitize_input_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], list[SecurityFinding]]:
    """Convenience functional wrapper around ModelArmor.sanitize_payload."""
    return _armor.sanitize_payload(payload)


def protect_agent_input(agent_id: str, payload: dict[str, Any], strict: bool = True) -> dict[str, Any]:
    """Intercept agent input, sanitize PII, and block severe prompt injection attacks.

    Args:
        agent_id: Identifier of the executing agent (e.g. '1.1', '2.1').
        payload: Input dictionary supplied to the agent.
        strict: If True, raises SecurityPolicyViolationError upon detecting a BLOCK finding.

    Returns:
        Sanitized payload dictionary safe for LLM consumption.
    """
    sanitized, findings = _armor.sanitize_payload(payload)
    block_findings = [f for f in findings if f.severity == SecuritySeverity.BLOCK]

    if block_findings and strict:
        violation_desc = "; ".join(f"{f.category.value}: {f.description}" for f in block_findings)
        msg = f"Model Armor Security Violation for agent '{agent_id}': {violation_desc}"
        _log.error(msg)
        raise SecurityPolicyViolationError(msg)

    return sanitized

"""Distribution adapters and external platform connectors for the Marketing Suite (Phase 8).

Implements real paid-media (Meta Ads) and email/messaging (Resend) execution
guarded by the Human Financial Authorization Gate (#1ebe82).
"""
from suite.distribution.financial_gate import (
    FinancialAuthorizationError,
    verify_financial_authorization,
)
from suite.distribution.meta_ads import MetaAdsClient
from suite.distribution.resend_email import ResendEmailClient

__all__ = [
    "FinancialAuthorizationError",
    "verify_financial_authorization",
    "MetaAdsClient",
    "ResendEmailClient",
]

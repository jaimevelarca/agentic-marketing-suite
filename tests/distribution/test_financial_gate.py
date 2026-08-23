"""Unit tests for the Human Financial Authorization Gate engine."""
import pytest
from infra import clients
from suite.distribution.financial_gate import (
    FinancialAuthorizationError,
    verify_financial_authorization,
)


@pytest.fixture(autouse=True)
def clean_memory():
    clients.reset_memory_store()
    yield
    clients.reset_memory_store()


def test_financial_gate_blocks_unapproved_block():
    clients.write_memory_block(
        "test-corp",
        "ad_campaign_log",
        {"authorization": {"status": "awaiting_authorization"}},
        gate_status="pending_review",
    )
    with pytest.raises(FinancialAuthorizationError, match="required: 'approved'"):
        verify_financial_authorization("test-corp", "meta_ads", proposed_spend_mxn=10000)


def test_financial_gate_blocks_awaiting_authorization():
    clients.write_memory_block(
        "test-corp",
        "ad_campaign_log",
        {"authorization": {"status": "awaiting_authorization"}},
        gate_status="approved",
    )
    with pytest.raises(FinancialAuthorizationError, match="authorization.status='awaiting_authorization'"):
        verify_financial_authorization("test-corp", "meta_ads", proposed_spend_mxn=10000)


def test_financial_gate_blocks_budget_ceiling_exceeded():
    clients.write_memory_block(
        "test-corp",
        "client_profile",
        {"name": "Test Corp", "confirmed_budget_mxn": 50000},
        gate_status="approved",
    )
    clients.write_memory_block(
        "test-corp",
        "ad_campaign_log",
        {"authorization": {"status": "authorized"}},
        gate_status="approved",
    )
    with pytest.raises(FinancialAuthorizationError, match="Financial ceiling exceeded"):
        verify_financial_authorization("test-corp", "meta_ads", proposed_spend_mxn=75000)


def test_financial_gate_allows_authorized_execution():
    clients.write_memory_block(
        "test-corp",
        "client_profile",
        {"name": "Test Corp", "confirmed_budget_mxn": 100000},
        gate_status="approved",
    )
    clients.write_memory_block(
        "test-corp",
        "ad_campaign_log",
        {"authorization": {"status": "authorized"}},
        gate_status="approved",
    )
    authorized, reason = verify_financial_authorization("test-corp", "meta_ads", proposed_spend_mxn=45000)
    assert authorized is True
    assert "Financial authorization verified" in reason

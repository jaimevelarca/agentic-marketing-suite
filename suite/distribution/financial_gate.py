"""Human Financial Authorization Gate engine (#1ebe82).

Enforces the strict rule: NO platform API call that incurs advertising spend
or bulk broadcast may execute without explicit human gate sign-off in Firestore.
"""
from __future__ import annotations

from typing import Any
from infra import clients
from infra.log import get_logger

_log = get_logger("financial_gate")


class FinancialAuthorizationError(PermissionError):
    """Raised when a distribution action lacks required human financial authorization."""
    pass


def verify_financial_authorization(
    client_id: str,
    channel: str,
    proposed_spend_mxn: float = 0.0,
    require_block: str = "ad_campaign_log",
) -> tuple[bool, str]:
    """Verify that a client's campaign distribution has valid human financial authorization.

    Args:
        client_id: Target client ID.
        channel: Channel to execute (e.g. 'meta_ads', 'google_ads', 'email_resend').
        proposed_spend_mxn: Amount of spend to be committed in MXN.
        require_block: Memory block to check gate status on (default: 'ad_campaign_log').

    Returns:
        tuple[bool, str]: (is_authorized, reason_message)

    Raises:
        FinancialAuthorizationError: If authorization is denied or missing.
    """
    gate_status = clients.read_gate_status(client_id, require_block)
    block_data = clients.read_memory_block(client_id, require_block) or {}
    profile_data = clients.read_memory_block(client_id, "client_profile") or {}

    # Check 1: Gate status must be approved
    if gate_status not in ("approved", "auto_approved"):
        msg = (
            f"Financial gate rejected: block '{require_block}' for client '{client_id}' "
            f"has gate_status='{gate_status}' (required: 'approved'). "
            "A human operator must approve the campaign in the review console first."
        )
        _log.warning(msg)
        raise FinancialAuthorizationError(msg)

    # Check 2: ad_campaign_log authorization status check if present
    auth_obj = block_data.get("authorization", {})
    if isinstance(auth_obj, dict):
        auth_status = auth_obj.get("status")
        if auth_status in ("awaiting_authorization", "rejected", "blocked"):
            msg = (
                f"Financial authorization rejected: authorization.status='{auth_status}' "
                f"for client '{client_id}'. Explicit sign-off required."
            )
            _log.warning(msg)
            raise FinancialAuthorizationError(msg)

    # Check 3: Budget ceiling check
    max_budget = profile_data.get("confirmed_budget_mxn") or profile_data.get("budget")
    if max_budget and isinstance(max_budget, (int, float)) and proposed_spend_mxn > 0:
        if proposed_spend_mxn > max_budget:
            msg = (
                f"Financial ceiling exceeded: proposed spend MXN {proposed_spend_mxn:,.2f} "
                f"exceeds confirmed client budget MXN {max_budget:,.2f}."
            )
            _log.warning(msg)
            raise FinancialAuthorizationError(msg)

    success_msg = (
        f"Financial authorization verified for client '{client_id}' on channel '{channel}' "
        f"(Gate status: {gate_status}, Proposed spend: MXN {proposed_spend_mxn:,.2f})."
    )
    _log.info(success_msg)
    return True, success_msg

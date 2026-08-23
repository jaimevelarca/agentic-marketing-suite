"""Per-domain MCP servers for the Digital Marketing AI Suite (ADR-04).

Four custom MCP servers serve memory blocks (and platform access) to the agents
as Cloud Run services. Rather than four near-identical files, one factory builds
the server for a named domain; the container picks its domain via MCP_DOMAIN.

    MCP_DOMAIN=audience_map python -m mcp.server     # serve audience/competitive blocks

Domains (project/specs/ARCHITECTURE.md "MCP servers"):
  - brand_core        : client_profile, brand_core            (read by all layers)
  - audience_map      : audience_segments, competitive_map    (read by L2-L4, L6)
  - campaign_registry : active_strategy, campaign_registry, content_calendar
  - platform_apis     : external paid-media / CRM access (Meta/Google/TikTok/HubSpot)

`mcp` (FastMCP) is an optional runtime dep for these services — add `mcp>=1.2`
to the image that runs them. Importing this module never requires it.
"""
from __future__ import annotations

import os
import sys
import pathlib

_SUITE = pathlib.Path(__file__).resolve().parents[1]
if str(_SUITE) not in sys.path:
    sys.path.append(str(_SUITE))


# Which memory blocks each data-domain server exposes.
DOMAIN_BLOCKS: dict[str, list[str]] = {
    "brand_core": ["client_profile", "brand_core"],
    "audience_map": ["audience_segments", "competitive_map"],
    "campaign_registry": ["active_strategy", "campaign_registry", "content_calendar"],
}


def _get_mcp_server_cls():
    try:
        from mcp.server.mcpserver import MCPServer
        return MCPServer
    except ImportError:
        try:
            from mcp.server.fastmcp import FastMCP
            return FastMCP
        except ImportError:
            from mcp.server import Server
            return Server


def build_memory_domain_server(domain: str):
    """Build an MCP server exposing read tools over a data domain's blocks,
    backed by infra.clients.read_memory_block (Firestore in prod, memory store offline)."""
    server_cls = _get_mcp_server_cls()
    from infra import clients

    blocks = DOMAIN_BLOCKS[domain]
    server = server_cls(f"acme-{domain}")

    @server.tool()
    def list_blocks() -> list[str]:
        """List the memory blocks this domain serves."""
        return blocks

    @server.tool()
    def get_block(client_id: str, block: str) -> dict | None:
        """Read one memory block for a client. `block` must be in this domain."""
        if block not in blocks:
            raise ValueError(f"{block} not served by domain {domain}; has {blocks}")
        return clients.read_memory_block(client_id, block)

    return server


def build_platform_apis_server():
    """MCP server fronting external distribution APIs (Meta Ads, Resend Email)
    guarded by the Human Financial Authorization Gate."""
    server_cls = _get_mcp_server_cls()
    from suite.distribution.meta_ads import MetaAdsClient
    from suite.distribution.resend_email import ResendEmailClient
    from suite.distribution.financial_gate import verify_financial_authorization

    server = server_cls("acme-platform-apis")
    meta_client = MetaAdsClient()
    resend_client = ResendEmailClient()


    @server.tool()
    def deploy_meta_campaign(client_id: str, name: str, daily_budget_mxn: float = 500.0, dry_run: bool = True) -> dict:
        """Create and configure a Meta ad campaign (dry-run simulation by default)."""
        return meta_client.create_campaign(client_id=client_id, name=name, daily_budget_mxn=daily_budget_mxn, dry_run=dry_run)

    @server.tool()
    def dispatch_email_campaign(client_id: str, subject: str, html_body: str, audience_segment: str = "all_active", dry_run: bool = True) -> dict:
        """Dispatch an email marketing broadcast via Resend (dry-run simulation by default)."""
        return resend_client.send_campaign(client_id=client_id, subject=subject, html_body=html_body, audience_segment=audience_segment, dry_run=dry_run)

    @server.tool()
    def fetch_ad_metrics(platform: str, account_id: str, since: str) -> dict:
        """Fetch campaign performance metrics for a paid media platform (meta|google|tiktok)."""
        return meta_client.fetch_ad_metrics(platform=platform, account_id=account_id, since=since)

    @server.tool()
    def fetch_email_metrics(client_id: str, campaign_id: str | None = None) -> dict:
        """Fetch email delivery, open, and click-through metrics from Resend."""
        return resend_client.fetch_email_metrics(client_id=client_id, campaign_id=campaign_id)

    @server.tool()
    def check_financial_authorization(client_id: str, channel: str, proposed_spend_mxn: float = 0.0) -> dict:
        """Verify if a client campaign has valid human financial authorization in Firestore (#1ebe82)."""
        try:
            authorized, reason = verify_financial_authorization(client_id, channel, proposed_spend_mxn)
            return {"authorized": authorized, "reason": reason}
        except Exception as exc:
            return {"authorized": False, "reason": str(exc)}

    return server



def main() -> int:
    domain = os.getenv("MCP_DOMAIN", "brand_core")
    if domain == "platform_apis":
        server = build_platform_apis_server()
    elif domain in DOMAIN_BLOCKS:
        server = build_memory_domain_server(domain)
    else:
        print(f"unknown MCP_DOMAIN={domain}; expected one of "
              f"{list(DOMAIN_BLOCKS) + ['platform_apis']}", file=sys.stderr)
        return 2
    server.run()  # serves over stdio / configured transport
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

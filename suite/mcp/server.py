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
    sys.path.insert(0, str(_SUITE))

# Which memory blocks each data-domain server exposes.
DOMAIN_BLOCKS: dict[str, list[str]] = {
    "brand_core": ["client_profile", "brand_core"],
    "audience_map": ["audience_segments", "competitive_map"],
    "campaign_registry": ["active_strategy", "campaign_registry", "content_calendar"],
}


def build_memory_domain_server(domain: str):
    """Build a FastMCP server exposing read tools over a data domain's blocks,
    backed by infra.clients.read_memory_block (Cloud SQL in prod, store offline)."""
    from mcp.server.fastmcp import FastMCP  # optional dep
    from infra import clients

    blocks = DOMAIN_BLOCKS[domain]
    server = FastMCP(f"acme-{domain}")

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
    """Scaffold MCP server fronting external paid-media + CRM APIs (Meta Marketing,
    Google Ads, TikTok Ads, HubSpot). Tools are stubs until the platform
    credentials (Secret Manager) and clients are wired in Phase 3/5."""
    from mcp.server.fastmcp import FastMCP  # optional dep
    server = FastMCP("acme-platform-apis")

    @server.tool()
    def fetch_ad_metrics(platform: str, account_id: str, since: str) -> dict:
        """Fetch campaign metrics for a platform (meta|google|tiktok). STUB."""
        raise NotImplementedError("platform API clients are wired in Phase 3/5 (DEL-30, 5.1)")

    @server.tool()
    def fetch_crm_leads(since: str) -> list[dict]:
        """Fetch new HubSpot leads since a timestamp. STUB."""
        raise NotImplementedError("HubSpot client is wired in Phase 5 (5.3 Lead Capture)")

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

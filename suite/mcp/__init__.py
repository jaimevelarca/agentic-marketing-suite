"""Custom MCP servers per data domain (ADR-04), deployed as Cloud Run services.

Per project/specs/ARCHITECTURE.md the Suite exposes brand/audience/campaign data
to the agents through MCP servers rather than direct DB coupling. `server.py`
builds a server for any domain from one parameterized factory; `MCP_DOMAIN`
selects which one a container runs.
"""

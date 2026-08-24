#!/usr/bin/env python3
"""CLI tool for compiling client proposals into standalone HTML presentation decks and executive detail reports.

Usage:
    PYTHONPATH=suite python -m scripts.compile_proposal --client <client_id>
    PYTHONPATH=suite python -m scripts.compile_proposal --client alonso-y-cia --theme path/to/theme.toml
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "suite") not in sys.path:
    sys.path.insert(0, str(_ROOT / "suite"))

from suite.rendering import compile_proposal, load_theme


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile interactive presentation deck and executive detail report."
    )
    parser.add_argument("--client", "-c", required=True, help="Client ID (e.g. 'acme', 'alonso-y-cia')")
    parser.add_argument("--theme", "-t", default=None, help="Optional path to custom theme.toml")
    parser.add_argument(
        "--out",
        "-o",
        default=None,
        help="Output directory (defaults to exports/proposals/<client_id>/)",
    )
    args = parser.parse_args()

    client_id = args.client.strip()
    out_dir = Path(args.out) if args.out else _ROOT / "exports" / "proposals" / client_id
    theme_obj = load_theme(args.theme) if args.theme else None

    print(f"Compiling proposal for client '{client_id}'...")
    res = compile_proposal(client_id, theme=theme_obj, out_dir=out_dir)

    print("\n✅ Proposal successfully compiled:")
    print(f"   • Presentation Deck: {res['presentation_path']}")
    print(f"   • Executive Detail:  {res['detail_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

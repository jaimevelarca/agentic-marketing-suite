"""High-level proposal and presentation compiler facade.

Compiles and exports both the interactive 9-act presentation deck and the
executive detail dossier for any client with one call.
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

from suite.rendering.detail_compiler import compile_detail_report
from suite.rendering.presentation_compiler import compile_presentation_deck
from suite.rendering.theme import Theme, derive_theme_from_profile, load_theme


def compile_proposal(
    client_id: str,
    memory_blocks: dict[str, Any] | None = None,
    theme: Theme | dict[str, Any] | str | Path | None = None,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Compile both presentation deck and detail report for a client.

    If out_dir is specified (or a default path is desired), writes both standalone
    HTML files to disk and returns their paths.
    """
    deck_html = compile_presentation_deck(client_id, memory_blocks=memory_blocks, theme=theme)
    detail_html = compile_detail_report(client_id, memory_blocks=memory_blocks, theme=theme)

    # Resolve theme for filename generation
    if theme is None:
        try:
            from infra import clients
        except ImportError:
            from suite.infra import clients  # type: ignore[no-redef]
        profile_block = (memory_blocks or {}).get("client_profile")
        if profile_block is None:
            profile_block = clients.read_memory_block(client_id, "client_profile")
        th = derive_theme_from_profile(
            profile_block,
            client_id=client_id,
        )
    elif isinstance(theme, Theme):
        th = theme
    else:
        th = load_theme(theme)

    safe_name = "".join(c for c in th.name if c.isalnum() or c in ("-", "_")).strip() or client_id
    today_str = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d")

    deck_filename = f"Plan_{safe_name}_QHHE_{today_str}.html"
    detail_filename = f"Detalle_{safe_name}_QHHE_{today_str}.html"

    result: dict[str, Any] = {
        "client_id": client_id,
        "client_name": th.name,
        "presentation_html": deck_html,
        "detail_html": detail_html,
        "presentation_filename": deck_filename,
        "detail_filename": detail_filename,
        "presentation_path": None,
        "detail_path": None,
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }

    if out_dir is not None:
        p_out = Path(out_dir)
        p_out.mkdir(parents=True, exist_ok=True)
        deck_file = p_out / deck_filename
        detail_file = p_out / detail_filename
        deck_file.write_text(deck_html, encoding="utf-8")
        detail_file.write_text(detail_html, encoding="utf-8")
        result["presentation_path"] = str(deck_file)
        result["detail_path"] = str(detail_file)

    return result

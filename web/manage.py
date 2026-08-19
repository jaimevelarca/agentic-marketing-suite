#!/usr/bin/env python
"""Django management entrypoint (console de revisión de la suite)."""
import os
import sys
from pathlib import Path

# The suite package lives at <repo>/suite with top-level modules (infra, agents,
# orchestration) — same PYTHONPATH=suite convention as the CLI entrypoints.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "suite"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)

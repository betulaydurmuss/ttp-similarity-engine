"""Shared helpers for the command-line entry points."""

from __future__ import annotations

import sys


def configure_stdout() -> None:
    """Force UTF-8 on stdout/stderr so Turkish output survives a Windows pipe."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

#!/usr/bin/env python3
"""Convenience launcher for the bundled Codex Session Scout skill script."""

from __future__ import annotations

import runpy
from pathlib import Path


def main() -> None:
    script = (
        Path(__file__).resolve().parent
        / "skills"
        / "codex-session-scout"
        / "scripts"
        / "codex_session_scout.py"
    )
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()

"""GUI entry: launches stdlib browser UI (no tkinter)."""

from __future__ import annotations

import traceback
from pathlib import Path


def main() -> None:
    try:
        from .webui import main as web_main

        web_main()
    except Exception:
        log = Path(__file__).resolve().parent.parent / "launch-error.log"
        try:
            log.write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
        raise


if __name__ == "__main__":
    main()

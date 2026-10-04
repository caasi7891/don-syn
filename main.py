"""Launch DON SYN, a local keyboard synthesizer."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _report(text):
    try:
        (ROOT / "error.log").write_text(text, encoding="utf-8")
    except OSError:
        pass
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("DON SYN", "시작하지 못했습니다.\n\n" + text[-1800:])
        root.destroy()
    except Exception:
        print(text)


def main():
    if "--test" in sys.argv:
        from synth.selftest import main as run_tests
        run_tests()
        return
    try:
        from synth.app import main as run_app
        run_app()
    except Exception:
        _report(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()

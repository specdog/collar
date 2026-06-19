"""
Dag CLI - Unified command-line interface for DAG Agent.

Provides subcommands for:
- dag chat          - Interactive chat (same as ./dag)
- dag gateway       - Run gateway in foreground
- dag gateway start - Start gateway service
- dag gateway stop  - Stop gateway service
- dag setup         - Interactive setup wizard
- dag status        - Show status of all components
- dag cron          - Manage cron jobs
"""

import os
import re
import sys
from pathlib import Path


def _read_pyproject_version() -> str:
    """Read version from pyproject.toml — single source of truth."""
    try:
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        if pyproject.exists():
            text = pyproject.read_text()
            m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
            if m:
                return m.group(1)
    except Exception:
        pass
    # Fallback: installed package metadata
    try:
        from importlib.metadata import version
        return version("collar")
    except Exception:
        return "0.0.0"


def _read_release_date() -> str:
    """Derive release date from git — always current."""
    import subprocess
    try:
        repo = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "HEAD"],
            capture_output=True, text=True, cwd=repo, timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


__version__ = _read_pyproject_version()
__release_date__ = _read_release_date()


def _ensure_utf8():
    """Force UTF-8 stdout/stderr to prevent UnicodeEncodeError crashes.

    Several environments select a legacy, non-UTF-8 encoding for the standard
    streams:

    - Windows services and terminals default to cp1252.
    - Linux hosts with a latin-1 / C / POSIX locale (common on minimal Debian
      installs and Raspberry Pi) select latin-1 or ASCII.

    The CLI prints box-drawing characters (┌│├└─) and the 🦴 glyph in the setup
    wizard, doctor, and status banners. Encoding those under a non-UTF-8 codec
    raises an unhandled UnicodeEncodeError that crashes the command before it
    can even start — e.g. `dag setup` on a fresh Pi.

    This runs at import time so it protects every CLI subcommand, on any
    platform. It re-wraps stdout/stderr as UTF-8 when their encoding is not
    already UTF-8, preferring TextIOWrapper.reconfigure() so the existing
    stream object is fixed in place (cached `sys.stdout` references keep
    working) and falling back to reopening the file descriptor with
    closefd=False (the CPython-recommended safe variant).

    No-op when the streams are already UTF-8: a healthy UTF-8 system sees no
    stream change and no environment mutation.

    Note: this is intentionally the earliest, platform-agnostic guard.
    dag_cli/stdio.py::configure_windows_stdio() runs later from the entry
    points and layers on the Windows-only extras (console code-page flip,
    EDITOR default, PATH augmentation); its stream reconfiguration is a
    harmless idempotent no-op once we have already repaired the streams here.
    """
    repaired = False

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        try:
            encoding = (getattr(stream, "encoding", "") or "").lower().replace("-", "")
            if encoding == "utf8":
                continue

            # Preferred: reconfigure the existing TextIOWrapper in place. This
            # preserves object identity so any code already holding a reference
            # to the old sys.stdout benefits from the repair too.
            reconfigure = getattr(stream, "reconfigure", None)
            if callable(reconfigure):
                reconfigure(encoding="utf-8", errors="replace")
                repaired = True
                continue

            # Fallback: reopen the underlying file descriptor as UTF-8. Used
            # for streams that don't expose reconfigure() (e.g. some wrapped
            # or replaced streams). closefd=False keeps the original fd open.
            new_stream = open(
                stream.fileno(), "w", encoding="utf-8",
                errors="replace", buffering=1, closefd=False,
            )
            setattr(sys, stream_name, new_stream)
            repaired = True
        except (AttributeError, OSError, ValueError):
            pass

    # Only nudge child processes toward UTF-8 when we actually detected a
    # non-UTF-8 locale. On a healthy UTF-8 host children inherit UTF-8 from the
    # locale already, so leave the environment untouched (minimal footprint).
    if repaired:
        os.environ.setdefault("PYTHONUTF8", "1")
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")


_ensure_utf8()

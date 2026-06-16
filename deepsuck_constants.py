"""Deepsuck constants — override Hermes home for isolated config."""

import os
import sys
from pathlib import Path


def _get_platform_default_deepsuck_home() -> Path:
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
        base = Path(local_appdata) if local_appdata else Path.home() / "AppData" / "Local"
        return base / "deepsuck"
    return Path.home() / ".deepsuck"


def get_deepsuck_home() -> Path:
    """Return the Deepsuck home directory."""
    env_override = os.environ.get("DEEPSUCK_HOME", "").strip()
    if env_override:
        return Path(env_override)
    return _get_platform_default_deepsuck_home()

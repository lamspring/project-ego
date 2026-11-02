"""Host-specific configuration kept outside the published runtime state."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
LOCAL = ROOT / "config" / "local.json"


def setting(name: str, default=None):
    if name in os.environ:
        return os.environ[name]
    if LOCAL.exists():
        data = json.loads(LOCAL.read_text(encoding="utf-8"))
        if name in data:
            return data[name]
    return default


def executable(name: str, env_name: str, windows_fallback: Path | None = None) -> str:
    configured = setting(env_name)
    if configured:
        return str(configured)
    found = shutil.which(name)
    if found:
        return found
    if windows_fallback and windows_fallback.exists():
        return str(windows_fallback)
    return name

"""Shared helpers for the session-rules hooks.

Both hooks are defensive by construction: they never raise, never block a
session, and always exit 0 with valid JSON on stdout. A hook that can break a
session is worse than no hook at all, so every failure path degrades to "emit
nothing".
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Directory in the host repo holding decision records.
DECISIONS_DIR = os.environ.get("SESSION_RULES_DECISIONS_DIR", "decisions")

# Filename of the short, always-re-emitted rules file inside that directory.
RULES_FILENAME = os.environ.get("SESSION_RULES_RULES_FILE", "RULES.md")

# How many of the most recent decision records to list in the session digest.
DIGEST_RECORD_LIMIT = int(os.environ.get("SESSION_RULES_DIGEST_LIMIT", "20"))

# A RULES.md longer than this is not re-emitted on every prompt — at that
# length it stops being a rule list and starts being a document, and paying
# for it on every turn is not worth it.
RULES_MAX_LINES = int(os.environ.get("SESSION_RULES_MAX_LINES", "30"))

# Record file extension considered a decision record.
RECORD_SUFFIX = ".md"


def read_hook_input() -> dict:
    """Read the hook payload from stdin. Never raises."""
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def resolve_project_dir(payload: dict) -> Path | None:
    """Best-effort project root: hook payload first, then the environment."""
    for key in ("cwd", "project_dir", "projectDir"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            candidate = Path(value)
            if candidate.is_dir():
                return candidate
    for env_key in ("CLAUDE_PROJECT_DIR", "PWD"):
        value = os.environ.get(env_key)
        if value:
            candidate = Path(value)
            if candidate.is_dir():
                return candidate
    return None


def decisions_dir(project_dir: Path) -> Path | None:
    """The host repo's decisions directory, or None when it does not exist."""
    try:
        candidate = project_dir / DECISIONS_DIR
        return candidate if candidate.is_dir() else None
    except Exception:
        return None


def record_title(path: Path) -> str:
    """First markdown heading in the record, falling back to the filename."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for _ in range(20):
                line = handle.readline()
                if not line:
                    break
                stripped = line.strip()
                if stripped.startswith("#"):
                    return stripped.lstrip("#").strip() or path.stem
    except Exception:
        pass
    return path.stem


def emit(event_name: str, additional_context: str | None) -> None:
    """Emit a valid hook response and exit 0, whatever happened upstream."""
    if additional_context:
        payload = {
            "hookSpecificOutput": {
                "hookEventName": event_name,
                "additionalContext": additional_context,
            }
        }
    else:
        payload = {}
    try:
        sys.stdout.write(json.dumps(payload))
    except Exception:
        sys.stdout.write("{}")
    sys.exit(0)

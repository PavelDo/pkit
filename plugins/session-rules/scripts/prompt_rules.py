#!/usr/bin/env python3
"""UserPromptSubmit hook: re-emit the host repo's short standing rules.

Rules stated once at session start decay as the context window fills. This hook
re-emits decisions/RULES.md verbatim on every prompt, but only while the file
stays short — beyond the line limit it is a document, not a rule list, and
paying for it every turn is not worth it.

No decisions/ directory, no RULES.md, an empty file, or a file over the limit:
emit nothing and exit 0.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    RULES_FILENAME,
    RULES_MAX_LINES,
    decisions_dir,
    emit,
    read_hook_input,
    resolve_project_dir,
)

EVENT = "UserPromptSubmit"


def build_rules_context(records_dir: Path) -> str | None:
    rules_path = records_dir / RULES_FILENAME
    if not rules_path.is_file():
        return None
    try:
        text = rules_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    stripped = text.strip()
    if not stripped:
        return None
    if len(stripped.splitlines()) > RULES_MAX_LINES:
        return None

    return (
        f"Standing rules for this repository (`{records_dir.name}/{RULES_FILENAME}`):\n\n"
        f"{stripped}"
    )


def main() -> None:
    try:
        payload = read_hook_input()
        project_dir = resolve_project_dir(payload)
        if project_dir is None:
            emit(EVENT, None)
        records_dir = decisions_dir(project_dir)
        if records_dir is None:
            emit(EVENT, None)
        emit(EVENT, build_rules_context(records_dir))
    except SystemExit:
        raise
    except Exception:
        emit(EVENT, None)


if __name__ == "__main__":
    main()

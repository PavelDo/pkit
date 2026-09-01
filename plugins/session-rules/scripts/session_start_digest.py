#!/usr/bin/env python3
"""SessionStart hook: surface the host repo's decision records into the session.

If the project has a decisions/ directory, emit a compact digest as
additionalContext: the titles of the most recent records, plus the contents of
decisions/RULES.md when it exists. If there is no decisions/ directory, emit
nothing and exit 0 — most repos do not use this convention and must not notice
the hook at all.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    DIGEST_RECORD_LIMIT,
    RECORD_SUFFIX,
    RULES_FILENAME,
    decisions_dir,
    emit,
    read_hook_input,
    record_title,
    resolve_project_dir,
)

EVENT = "SessionStart"


def build_digest(records_dir: Path) -> str | None:
    try:
        records = sorted(
            (
                path
                for path in records_dir.iterdir()
                if path.is_file()
                and path.suffix == RECORD_SUFFIX
                and path.name != RULES_FILENAME
            ),
            key=lambda path: path.name,
            reverse=True,
        )
    except Exception:
        return None

    sections: list[str] = []

    rules_path = records_dir / RULES_FILENAME
    if rules_path.is_file():
        try:
            rules_text = rules_path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            rules_text = ""
        if rules_text:
            sections.append(
                f"Standing rules from `{records_dir.name}/{RULES_FILENAME}`:\n\n{rules_text}"
            )

    if records:
        shown = records[:DIGEST_RECORD_LIMIT]
        listing = "\n".join(f"- {path.name} — {record_title(path)}" for path in shown)
        header = (
            f"Most recent decision records in `{records_dir.name}/` "
            f"({len(shown)} of {len(records)}):"
        )
        sections.append(f"{header}\n{listing}")

    if not sections:
        return None

    preamble = (
        "This repository keeps append-only decision records. "
        "Read the relevant record before revisiting a decision it covers, and "
        "add a new record rather than editing an existing one."
    )
    return "\n\n".join([preamble, *sections])


def main() -> None:
    try:
        payload = read_hook_input()
        project_dir = resolve_project_dir(payload)
        if project_dir is None:
            emit(EVENT, None)
        records_dir = decisions_dir(project_dir)
        if records_dir is None:
            emit(EVENT, None)
        emit(EVENT, build_digest(records_dir))
    except SystemExit:
        raise
    except Exception:
        emit(EVENT, None)


if __name__ == "__main__":
    main()

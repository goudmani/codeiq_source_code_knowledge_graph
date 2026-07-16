#!/usr/bin/env python3
"""
file_utils.py

Reads source files out of the locally-cloned raw repos (data/raw/<tag>/,
populated by src/clone_raw/clone_raw.py) so the UI can display real code --
not just the possibly-truncated snippet a tool happened to return. A source
hit's "file" field (e.g. "src/App.tsx") is a path relative to data/raw/<tag>/,
mirroring how clone_raw.py lays files out on disk.

Every lookup takes an explicit `tag` (the indexed repo snapshot a given
answer/source came from -- see app.py's repo selector) rather than assuming a
single fixed repo, since the UI lets users switch between multiple indexed
repos.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = PROJECT_ROOT / "data" / "raw"

MAX_FILE_LINES = 6000  # safety cap for pathological files; source files are never this long


@lru_cache(maxsize=512)
def _read_lines(tag: str, file_rel_path: str) -> tuple[str, ...] | None:
    repo_root = (RAW_ROOT / tag).resolve()
    path = (repo_root / file_rel_path).resolve()
    try:
        # Guard against a crafted path escaping the repo's raw root.
        path.relative_to(repo_root)
    except ValueError:
        return None
    try:
        return tuple(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return None


def file_exists(tag: str, file_rel_path: str | None) -> bool:
    if not file_rel_path:
        return False
    return _read_lines(tag, file_rel_path) is not None


def read_range(tag: str, file_rel_path: str, start_line: int | None, end_line: int | None) -> list[str]:
    """1-indexed, inclusive line range -- mirrors how entities.jsonl records startLine/endLine."""
    lines = _read_lines(tag, file_rel_path)
    if not lines:
        return []
    start = max(1, start_line or 1)
    end = min(len(lines), end_line or len(lines))
    if end < start:
        end = start
    return list(lines[start - 1 : end])


def read_full_file(tag: str, file_rel_path: str) -> tuple[list[str], bool]:
    """Returns (lines, truncated)."""
    lines = _read_lines(tag, file_rel_path)
    if not lines:
        return [], False
    if len(lines) > MAX_FILE_LINES:
        return list(lines[:MAX_FILE_LINES]), True
    return list(lines), False


def line_count(tag: str, file_rel_path: str) -> int:
    lines = _read_lines(tag, file_rel_path)
    return len(lines) if lines else 0

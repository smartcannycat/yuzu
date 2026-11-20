"""Atomic disk writes and bounded cache directory pruning helpers."""

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


def atomic_write_text(
    path: Path,
    content: str,
    *,
    prefix: str = ".tmp_",
    suffix: str = ".tmp",
) -> None:
    """Write text atomically to ``path`` using a temp file in the same directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=prefix, suffix=suffix)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        tmp_path.replace(path)
    except BaseException:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def atomic_write_json(
    path: Path,
    payload: Any,
    *,
    prefix: str = ".tmp_",
    indent: int | None = None,
) -> None:
    """Serialize ``payload`` to JSON and persist atomically."""
    serialized = json.dumps(payload, ensure_ascii=False, indent=indent)
    atomic_write_text(path, serialized, prefix=prefix, suffix=".json")


def enforce_cache_limits(
    cache_dir: Path,
    *,
    max_age_seconds: float | None = None,
    max_bytes: int | None = None,
    pattern: str = "*.json",
) -> None:
    """Remove expired cache files and prune oldest entries when total size exceeds max_bytes."""
    if not cache_dir.is_dir():
        return

    now = time.time()
    entries: list[tuple[float, int, Path]] = []
    for entry in cache_dir.glob(pattern):
        if entry.name.startswith(".tmp_") or not entry.is_file():
            continue
        try:
            st = entry.stat()
        except OSError:
            continue
        if (
            max_age_seconds is not None
            and max_age_seconds > 0
            and (now - st.st_mtime) > max_age_seconds
        ):
            entry.unlink(missing_ok=True)
            continue
        entries.append((st.st_mtime, st.st_size, entry))

    if max_bytes is None or max_bytes < 0:
        return

    total_bytes = sum(size for _, size, _ in entries)
    if total_bytes <= max_bytes:
        return

    entries.sort(key=lambda item: item[0])
    for _, size, entry in entries:
        if total_bytes <= max_bytes:
            break
        try:
            entry.unlink(missing_ok=True)
            total_bytes -= size
        except OSError:
            continue

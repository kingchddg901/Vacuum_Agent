"""Filesystem read/write for TraceRun JSON records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TRACE_SCHEMA_VERSION = 1
_TRACES_SUBDIR = "traces"


def _traces_dir(base_mapping_dir: Path, vacuum_slug: str) -> Path:
    """Return (and create) the traces directory for one vacuum."""
    path = base_mapping_dir / vacuum_slug / _TRACES_SUBDIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_trace_run(
    base_mapping_dir: Path,
    vacuum_slug: str,
    run: dict[str, Any],
) -> Path:
    """Write one TraceRun dict to disk.

    The run dict must already be fully formed — this function
    does not validate or modify content. Returns the path written.
    """
    traces_dir = _traces_dir(base_mapping_dir, vacuum_slug)
    run_id = str(run["run_id"])
    path = traces_dir / f"{run_id}.json"
    path.write_text(json.dumps(run, indent=2), encoding="utf-8")
    return path


def load_trace_run(
    base_mapping_dir: Path,
    vacuum_slug: str,
    run_id: str,
) -> dict[str, Any] | None:
    """Load one TraceRun by run_id. Returns None if not found or unreadable."""
    traces_dir = _traces_dir(base_mapping_dir, vacuum_slug)
    path = traces_dir / f"{run_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def list_trace_run_ids(
    base_mapping_dir: Path,
    vacuum_slug: str,
) -> list[str]:
    """Return all stored run_ids for one vacuum, sorted ascending by name.

    Sorting by name is equivalent to sorting by capture time because
    run IDs are UTC-timestamp-prefixed.
    """
    traces_dir = _traces_dir(base_mapping_dir, vacuum_slug)
    return sorted(
        p.stem for p in traces_dir.glob("*.json")
    )


def delete_trace_run(
    base_mapping_dir: Path,
    vacuum_slug: str,
    run_id: str,
) -> bool:
    """Delete one trace run file. Returns True if deleted, False if not found."""
    traces_dir = _traces_dir(base_mapping_dir, vacuum_slug)
    path = traces_dir / f"{run_id}.json"
    if not path.exists():
        return False
    path.unlink()
    return True

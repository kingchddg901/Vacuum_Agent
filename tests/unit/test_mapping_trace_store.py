"""Unit tests for mapping/trace_store.py — filesystem TraceRun store (tmp_path).

Coverage targets
----------------
[TST-1]  _traces_dir creates the nested traces directory.
[TST-2]  write_trace_run writes <run_id>.json and returns its path.
[TST-3]  write/load round-trips the run dict.
[TST-4]  load_trace_run returns None for a missing run.
[TST-5]  load_trace_run returns None for unreadable/corrupt JSON.
[TST-6]  list_trace_run_ids returns run ids sorted ascending.
[TST-7]  list_trace_run_ids returns [] when none stored.
[TST-8]  delete_trace_run removes the file and returns True.
[TST-9]  delete_trace_run returns False when the run is missing.
"""

from __future__ import annotations

from pathlib import Path

from custom_components.eufy_vacuum.mapping.trace_store import (
    _TRACES_SUBDIR,
    _traces_dir,
    delete_trace_run,
    list_trace_run_ids,
    load_trace_run,
    write_trace_run,
)


_SLUG = "alfred"


def _run(run_id: str) -> dict:
    return {"run_id": run_id, "schema_version": 1, "samples": [{"x": 1, "y": 2}]}


def test_traces_dir_created(tmp_path: Path):
    """[TST-1]"""
    d = _traces_dir(tmp_path, _SLUG)
    assert d.exists() and d.is_dir()
    assert d == tmp_path / _SLUG / _TRACES_SUBDIR


def test_write_returns_path(tmp_path: Path):
    """[TST-2]"""
    path = write_trace_run(tmp_path, _SLUG, _run("r1"))
    assert path.exists()
    assert path.name == "r1.json"


def test_write_load_roundtrip(tmp_path: Path):
    """[TST-3]"""
    write_trace_run(tmp_path, _SLUG, _run("r1"))
    loaded = load_trace_run(tmp_path, _SLUG, "r1")
    assert loaded == _run("r1")


def test_load_missing_returns_none(tmp_path: Path):
    """[TST-4]"""
    assert load_trace_run(tmp_path, _SLUG, "nope") is None


def test_load_corrupt_returns_none(tmp_path: Path):
    """[TST-5]"""
    d = _traces_dir(tmp_path, _SLUG)
    (d / "bad.json").write_text("{not valid json", encoding="utf-8")
    assert load_trace_run(tmp_path, _SLUG, "bad") is None


def test_list_sorted(tmp_path: Path):
    """[TST-6]"""
    for rid in ["2026-01-02", "2026-01-01", "2026-01-03"]:
        write_trace_run(tmp_path, _SLUG, _run(rid))
    assert list_trace_run_ids(tmp_path, _SLUG) == ["2026-01-01", "2026-01-02", "2026-01-03"]


def test_list_empty(tmp_path: Path):
    """[TST-7]"""
    assert list_trace_run_ids(tmp_path, _SLUG) == []


def test_delete_found(tmp_path: Path):
    """[TST-8]"""
    write_trace_run(tmp_path, _SLUG, _run("r1"))
    assert delete_trace_run(tmp_path, _SLUG, "r1") is True
    assert load_trace_run(tmp_path, _SLUG, "r1") is None


def test_delete_missing(tmp_path: Path):
    """[TST-9]"""
    assert delete_trace_run(tmp_path, _SLUG, "ghost") is False

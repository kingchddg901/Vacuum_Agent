"""Unit tests for the decision log emitter.

Coverage targets
----------------
[DL-1]  emit writes `[event_id] {json}` at DEBUG.
[DL-2]  emit is a no-op when DEBUG is off (the hot-path guard).
[DL-3]  params are sorted, so two captures of the same decision diff cleanly.
[DL-4]  emit never raises — not on unserializable params, not on anything.
[DL-5]  oversized params are capped rather than flooding the ring.
[DL-6]  the event id is the anchor: prose is absent by construction.

These assert the CONTRACT (id + params), never wording — that separation is the
whole reason the id exists, so a test that froze prose would defeat it.
"""

from __future__ import annotations

import json
import logging

import pytest

from custom_components.eufy_vacuum import decision_log
from custom_components.eufy_vacuum.decision_log import MAX_PARAMS_CHARS, emit

_LOGGER_NAME = "custom_components.eufy_vacuum.decision_log"


def _records(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == _LOGGER_NAME]


def test_emit_writes_id_and_params(caplog):
    """[DL-1]"""
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        emit("phase.segment.reject", gate="count", expected=2, got=3)
    msgs = _records(caplog)
    assert len(msgs) == 1
    assert msgs[0].startswith("[phase.segment.reject] ")
    payload = json.loads(msgs[0].split("] ", 1)[1])
    assert payload == {"expected": 2, "gate": "count", "got": 3}


def test_emit_noop_when_debug_off(caplog):
    """[DL-2] The guard that keeps this free on per-sample paths."""
    with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
        emit("phase.segment.reject", gate="count")
    assert _records(caplog) == []


def test_params_are_sorted(caplog):
    """[DL-3] Stable key order — a capture is diffable across runs."""
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        emit("x.y.z", zebra=1, alpha=2, mike=3)
    body = _records(caplog)[0].split("] ", 1)[1]
    assert body == '{"alpha":2,"mike":3,"zebra":1}'


def test_emit_survives_unserializable_params(caplog):
    """[DL-4] A diagnostic that raises is worse than no diagnostic."""

    class Hostile:
        def __repr__(self):  # pragma: no cover - exercised via json default=str
            raise RuntimeError("no repr for you")

    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        emit("x.y.z", obj=Hostile())  # must not raise
    # It logged something or nothing; the contract is only that it returned.
    assert True


def test_emit_never_raises_on_bad_event_id(caplog):
    """[DL-4] Even a non-string id must not take a live run down."""
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        emit(None)  # type: ignore[arg-type]
        emit("")
    assert True


def test_oversized_params_are_capped(caplog):
    """[DL-5] One careless caller must not flood the ring."""
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        emit("x.y.z", blob="A" * (MAX_PARAMS_CHARS * 3))
    body = _records(caplog)[0].split("] ", 1)[1]
    assert body.endswith("...<elided>")
    assert len(body) <= MAX_PARAMS_CHARS + len("...<elided>")


def test_datetime_degrades_to_text_rather_than_failing(caplog):
    """[DL-4] default=str: an exotic value costs fidelity, never the record."""
    from datetime import datetime, timezone

    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        emit("x.y.z", at=datetime(2026, 8, 3, tzinfo=timezone.utc))
    payload = json.loads(_records(caplog)[0].split("] ", 1)[1])
    assert payload["at"].startswith("2026-08-03")


@pytest.mark.parametrize("event_id", [
    "phase.segment.reject",
    "phase.segment.ok",
    "phase.advance.refuse",
    "phase.capture.slice",
    "lifecycle.finalize.suppress",
])
def test_event_ids_are_area_operation_outcome(event_id, caplog):
    """[DL-6] The taxonomy is three dot-separated lowercase parts.

    Asserted so a drifting id (`phaseSegmentReject`, `phase.segment`) fails here
    rather than quietly becoming un-greppable in a support capture.
    """
    parts = event_id.split(".")
    assert len(parts) == 3, event_id
    assert all(p and p == p.lower() and p.replace("_", "").isalnum() for p in parts)
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        emit(event_id, k=1)
    assert _records(caplog)[0].startswith(f"[{event_id}] ")


def test_no_prose_in_the_record(caplog):
    """[DL-6] The record is an id plus JSON and nothing else.

    If a caller ever starts building sentences, the wording becomes the contract
    again and the whole rewrite-freely property is lost.
    """
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        emit("phase.segment.reject", gate="count", expected=2, got=3)
    msg = _records(caplog)[0]
    head, _, body = msg.partition("] ")
    assert head.startswith("[")
    assert body.startswith("{") and body.endswith("}")
    json.loads(body)


def test_module_logger_is_the_package_tree():
    """The flight recorder isolates one package logger tree; this must sit inside
    it or captures silently miss every decision record."""
    assert decision_log._LOGGER.name.startswith("custom_components.eufy_vacuum")

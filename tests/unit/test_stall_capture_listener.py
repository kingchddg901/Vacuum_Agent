"""Stall capture — the opt-in consumer of EVENT_STALL_DETECTED (issue #47).

The renderer is covered separately (`test_stall_capture_render.py`); this file covers the
decisions AROUND it, which is where the user-visible behaviour lives: whether the feature
is armed, where the file lands, and what the message says.

Coverage targets
----------------
[SL-1] absent arming is OFF — an upgrade never starts writing images of someone's home.
[SL-2] the path is per (vacuum, map) and STABLE, so an automation can hardcode it.
[SL-3] a Roborock map id (a NAME with a space) is sanitised into a usable filename.
[SL-4] the map label prefers the brand's DECLARED entity, and honestly falls back to the id.
[SL-5] an unusable state (unknown/unavailable) is not a label.
[SL-6] render-data geometry is passed through, never re-derived.
[SL-7] absent room_pixels yields None rather than a partial payload.
[SL-8] the trail is read from the pose ring: null anchors dropped, order preserved, and
       the ±window is the one the caller asked for.
[SL-9] the window comes from the brand's DECLARED pose cadence, not a constant.
[SL-10] the write is DURABLE (fsync before rename) and leaves no orphan tmp on failure.
[SL-11] a brand declaring active_map as a CANDIDATE LIST still gets a label.
[SL-12] registration is a HAND-OFF: a fired event really reaches the capture.
"""

from __future__ import annotations

import base64
import os
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from custom_components.eufy_vacuum.listeners import stall_capture as sc


class _FakeManager:
    def __init__(self, data):
        self.data = data


# ---------------------------------------------------------------------------
# arming
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bucket,expected",
    [
        ({}, False),                                  # never configured
        ({"stall_capture_enabled": False}, False),    # explicitly off
        ({"stall_capture_enabled": True}, True),      # armed
    ],
)
def test_absent_arming_is_off(bucket, expected):
    """[SL-1] Absent means OFF, not "default on".

    This feature writes a cropped floor-plan of the user's home to disk and raises a
    notification. Inheriting that from an upgrade — because the key simply was not there
    yet — is the one behaviour it must never have.
    """
    mgr = _FakeManager({"vacuums": {"vacuum.alfred": bucket}})

    assert sc.is_enabled(mgr, "vacuum.alfred") is expected


def test_a_broken_store_disarms_rather_than_raises():
    """[SL-1] This is read on a job-lifecycle path; unreadable state must not throw."""
    class _Broken:
        @property
        def data(self):
            raise RuntimeError("store unavailable")

    assert sc.is_enabled(_Broken(), "vacuum.alfred") is False


# ---------------------------------------------------------------------------
# where the file lands
# ---------------------------------------------------------------------------

def test_path_is_per_vacuum_per_map_and_stable():
    """[SL-2] One file per (vacuum, map), overwritten — no timestamp in the name.

    Stability is the feature: no accumulation to prune, and an automation can hardcode
    the path instead of parsing it out of an event.
    """
    a = sc.capture_path("/config", "vacuum.alfred", "12")
    b = sc.capture_path("/config", "vacuum.alfred", "12")
    other_map = sc.capture_path("/config", "vacuum.alfred", "7")
    other_vac = sc.capture_path("/config", "vacuum.ivy", "12")

    assert a == b, "the same vacuum/map must always resolve to the same file"
    assert a.replace("\\", "/").endswith("eufy_vacuum/learning/alfred/stall/12.png")
    assert a != other_map and a != other_vac


def test_a_roborock_map_name_is_sanitised_into_a_filename():
    """[SL-3] Roborock's map id is a NAME ("Main floor"), not a number.

    Treating an id as filename-safe works on Eufy and produces a path with a space (or
    worse, a separator) on Roborock.
    """
    p = sc.capture_path("/config", "vacuum.ivy", "Main floor").replace("\\", "/")

    assert p.endswith("eufy_vacuum/learning/ivy/stall/Main_floor.png")


def test_a_hostile_map_id_cannot_escape_the_directory():
    """[SL-3] Separators are replaced, so a map id can never traverse."""
    p = sc.capture_path("/config", "vacuum.ivy", "../../etc/passwd").replace("\\", "/")

    assert "/etc/passwd" not in p
    assert p.endswith("eufy_vacuum/learning/ivy/stall/etc_passwd.png")


# ---------------------------------------------------------------------------
# the message's map label
# ---------------------------------------------------------------------------

def test_map_label_prefers_the_declared_entity(monkeypatch):
    """[SL-4] Roborock declares select.<id>_selected_map, whose state IS the name.

    ⚠ THE `map_id` MUST DIFFER FROM THE EXPECTED LABEL. This test passed `map_id`
    "Main floor" until 2026-11-08 — exactly the string it asserts — so the fallback
    `return str(map_id)` satisfied it and the test stayed GREEN with the ENTIRE declared-
    entity read deleted. Found by ablating that read while verifying [SL-11]: nothing in
    the file could see the branch it was named for. An id that is not the answer is the
    whole discriminator here.
    """
    monkeypatch.setattr(
        sc, "get_adapter_value",
        lambda vid, *a, **kw: "select.ivy_selected_map",
    )

    class _S:
        state = "Main floor"

    class _Hass:
        class states:
            @staticmethod
            def get(_e):
                return _S()

    assert sc.map_label(_Hass(), "vacuum.ivy", "7") == "Main floor"


def test_map_label_falls_back_to_the_id_when_nothing_is_declared(monkeypatch):
    """[SL-4] Eufy declares only the numeric active_map sensor.

    The friendlier "Home (ID: 12)" lives on the fork's switch_map select, which the Eufy
    adapter does not declare. Guessing that entity id to get a nicer string would be the
    brand-ism this project keeps removing — so the id is what we honestly show.
    """
    monkeypatch.setattr(sc, "get_adapter_value", lambda vid, *a, **kw: None)

    class _Hass:
        class states:
            @staticmethod
            def get(_e):
                return None

    assert sc.map_label(_Hass(), "vacuum.alfred", "12") == "12"


@pytest.mark.parametrize("bad", ["unknown", "unavailable", "none", "", "   "])
def test_an_unusable_state_is_not_a_label(monkeypatch, bad):
    """[SL-5] "Alfred likely stalled in Kitchen on unknown" is worse than showing the id."""
    monkeypatch.setattr(
        sc, "get_adapter_value", lambda vid, *a, **kw: "sensor.alfred_active_map"
    )

    class _S:
        state = bad

    class _Hass:
        class states:
            @staticmethod
            def get(_e):
                return _S()

    assert sc.map_label(_Hass(), "vacuum.alfred", "12") == "12"


# ---------------------------------------------------------------------------
# [SL-11] the candidate-LIST declaration
#
# `entities.active_map` arrives in TWO SHAPES from the same key, and the files that
# declare them declare both: every code adapter sets `entities.active_map` to a bare
# string (eufy/adapter.py:262, dreame/adapter.py:170, roborock/adapter.py:820) and a
# one-element LIST under `entity_candidates` (197, 105, 430). The normalisation at the
# top of `map_label` is what lets the second shape through, and `isinstance(x,
# (list, tuple))` on an entity id occurs EXACTLY ONCE in `custom_components/` -- none
# of the other ~100 `entities.*` reads needs it.
#
# NO INCIDENT BEHIND IT, and it is not recorded here as a replay: `git log -S` puts
# the guard in the file's FIRST commit (76b79e78), not in a fix. What makes it
# reachable rather than decorative is that
# `adapters/config_loader.load_stored_adapter_configs` registers a stored `.storage`
# config with no schema validation (only an outer `isinstance(config, dict)`), and
# `get_adapter_value` returns `node.get(key)` verbatim.
# ---------------------------------------------------------------------------

def test_map_label_resolves_a_candidate_list_to_its_first_entity(monkeypatch):
    """[SL-11] A list declaration resolves to its FIRST element, not merely to one.

    The fake resolves a state for the first id and None for anything else, so a
    `[-1]` or an any-of implementation fails rather than passing on a one-element
    list.

    RED: `entity_id = entity_id[-1] if entity_id else None` -- measured red; and
    deleting the normalisation entirely leaves `entity_id` a list, `isinstance(...,
    str)` False, and the label falls back to the id.
    """
    monkeypatch.setattr(
        sc, "get_adapter_value",
        lambda vid, *a, **kw: ["select.ivy_selected_map", "select.ivy_other_map"],
    )

    class _Hass:
        class states:
            @staticmethod
            def get(entity_id):
                if entity_id == "select.ivy_selected_map":
                    return SimpleNamespace(state="Main floor")
                return None

    assert sc.map_label(_Hass(), "vacuum.ivy", "7") == "Main floor"


def test_map_label_falls_back_when_the_candidate_list_is_empty(monkeypatch):
    """[SL-11] An EMPTY declaration resolves to the id rather than raising.

    RED, AND IT IS NOT THE ONE THE OBVIOUS ABLATION GIVES: deleting the whole
    normalisation leaves this GREEN -- `isinstance([], str)` is already False, so
    control reaches `return str(map_id)` by the same route. The one input that
    separates this arm is dropping only the emptiness ternary (`entity_id =
    entity_id[0]`), which raises `IndexError: list index out of range`. Measured both
    ways while verifying this pair.

    THE RAISING STUB BELOW IS A TRIPWIRE, NOT THE OBSERVABLE, and saying so is the
    point: it cannot fire in ANY variant (with the guard `entity_id` is None, without
    it `[]`, and `isinstance` rejects both before `hass.states.get` is reached). An
    earlier draft of this test claimed the stub proved the short-circuit. It proves
    nothing, and an assertion that cannot see the thing it names is the trap this
    campaign keeps paying for. What is asserted is the behaviour: no raise, and the
    id comes back.
    """
    monkeypatch.setattr(sc, "get_adapter_value", lambda vid, *a, **kw: [])

    class _Hass:
        class states:
            @staticmethod
            def get(_e):
                raise AssertionError("an empty declaration must not be looked up")

    assert sc.map_label(_Hass(), "vacuum.alfred", "7") == "7"


# ---------------------------------------------------------------------------
# [SL-12] the dispatch hand-off
#
# `register()` was reached by the setup tests, but `_on_stall` -- the callback it
# subscribes -- was invoked by NOTHING: the only proof this listener dispatched
# anything was a static call site. That is
# `feedback_audit_callsite_reachability` in its runtime form, and
# `test_receipts_happy_path`'s own header records the same split being found inside
# the instrument built to detect it ("a call SITE exists, not that it ever RUNS").
#
# The three bus-level stall tests (test_manager_progress, test_stuck_watch_tick,
# test_services_stall_capture) FIRE the event but never `register()` the listener,
# and the four receipts tests await `_capture` directly -- so the hand-off between
# them was the one link nothing crossed.
# ---------------------------------------------------------------------------

def _dispatch_hass():
    """A hass that records what was subscribed and what was scheduled, nothing more."""
    listened: list = []
    scheduled: list = []

    def _listen(event_type, callback):
        listened.append((event_type, callback))
        return lambda: None

    return SimpleNamespace(
        data={},
        bus=SimpleNamespace(async_listen=_listen),
        async_create_task=scheduled.append,
    ), listened, scheduled


async def test_a_detected_stall_is_handed_to_the_capture(monkeypatch):
    """[SL-12] The subscription really runs the capture, and hands it a COPY.

    Two claims, each with its own red input:

    * the hand-off -- RED if `hass.async_create_task(_run())` is dropped: nothing is
      scheduled and `seen` stays empty.
    * the COPY at `data = dict(event.data or {})` -- RED if the `dict(...)` is
      dropped: the capture then reads the bus's own dict, which has moved on by the
      time the task runs. This is the only assertion here that can tell a copy from
      an alias, and `_capture` runs on a LATER tick than the callback, so the window
      is real rather than theoretical.

    `_capture` is replaced rather than driven: what is under test is the dispatch,
    and the capture's own behaviour is pinned by the four receipts tests.
    """
    seen: list[dict] = []

    async def _fake_capture(_hass, data):
        seen.append(data)

    monkeypatch.setattr(sc, "_capture", _fake_capture)

    hass, listened, scheduled = _dispatch_hass()
    sc.register(hass)

    assert [ev for ev, _cb in listened] == [sc.EVENT_STALL_DETECTED], listened
    _ev, on_stall = listened[0]

    payload = {"vacuum_entity_id": "vacuum.ivy", "map_id": "Main floor", "room_id": 27}
    on_stall(SimpleNamespace(data=payload))
    assert len(scheduled) == 1, "the callback did not hand the capture to the loop"

    # The bus's dict moves on BEFORE the scheduled task runs -- which is exactly the
    # ordering the real loop produces, since `_on_stall` returns immediately.
    payload["room_id"] = 99
    await scheduled[0]

    assert seen == [{"vacuum_entity_id": "vacuum.ivy", "map_id": "Main floor",
                     "room_id": 27}], seen


async def test_an_event_with_no_data_is_dispatched_as_an_empty_payload(monkeypatch):
    """[SL-12] `event.data or {}` -- a dataless fire declines, it does not raise.

    `hass.bus.async_fire(EVENT_STALL_DETECTED)` with no payload is reachable from any
    user automation, and `dict(None)` is a TypeError inside a callback whose only
    protection is the blanket `except` in `_run`. So the empty payload has to reach
    `_capture`, which declines `no_room` for it.

    RED: drop the `or {}` -- `dict(None)` raises and `seen` stays empty.
    """
    seen: list[dict] = []

    async def _fake_capture(_hass, data):
        seen.append(data)

    monkeypatch.setattr(sc, "_capture", _fake_capture)

    hass, listened, scheduled = _dispatch_hass()
    sc.register(hass)
    _ev, on_stall = listened[0]

    on_stall(SimpleNamespace(data=None))
    await scheduled[0]

    assert seen == [{}], seen


# ---------------------------------------------------------------------------
# geometry pass-through
# ---------------------------------------------------------------------------

def test_render_geometry_is_passed_through_not_re_derived():
    """[SL-6] The raster is ro_* sized, OFFSET into the canvas, and its byte is shifted.

    Re-deriving any of that is exactly how the renderer was wrong the first time, so the
    consumer forwards the adapter's own block verbatim.
    """
    payload = sc._render_payload({
        "room_pixels": base64.b64encode(b"\x00" * (4 * 3)).decode(),
        "ro_width": 4, "ro_height": 3,
        "width": 40, "height": 30,
        "ro_dx": 7, "ro_dy": 9,
        "rid_shift": 2, "flip_y": True,
    })

    assert payload is not None
    assert payload["ro_width"] == 4 and payload["ro_height"] == 3
    assert payload["canvas_width"] == 40 and payload["canvas_height"] == 30
    assert payload["ro_dx"] == 7 and payload["ro_dy"] == 9
    assert payload["rid_shift"] == 2 and payload["flip_y"] is True


def test_roborock_shaped_data_defaults_the_offset_and_shift():
    """[SL-6] Roborock's raster IS its canvas: no offset, ids already resolved."""
    payload = sc._render_payload({
        "room_pixels": base64.b64encode(b"\x00" * (5 * 5)).decode(),
        "width": 5, "height": 5,
    })

    assert payload is not None
    assert payload["ro_width"] == 5 and payload["canvas_width"] == 5
    assert payload["ro_dx"] == 0 and payload["ro_dy"] == 0
    assert payload["rid_shift"] == 0 and payload["flip_y"] is False


@pytest.mark.parametrize(
    "render",
    [
        {},                                        # nothing present
        {"room_pixels": ""},                       # declared empty
        {"room_pixels": "!!not base64!!"},         # undecodable
        {"room_pixels": base64.b64encode(b"x").decode(), "width": 0, "height": 0},
    ],
)
def test_unusable_render_data_yields_none(render):
    """[SL-7] None, never a partial payload the renderer would misread as geometry."""
    assert sc._render_payload(render) is None


# ---------------------------------------------------------------------------
# the trail, read out of the pose ring
#
# _trail_from_ring had NO test anywhere — neither this file nor any other mentioned
# "anchor" or "trail" — which is how a brand that recorded no anchors at all read as a
# working feature: the function did exactly what it was written to do with an empty ring.
# ---------------------------------------------------------------------------

_WHEN = datetime(2026, 8, 9, 12, 0, 0, tzinfo=timezone.utc)


def _ring(monkeypatch, samples):
    """Stub the pose ring and capture the window the caller asked it for."""
    seen: dict = {}

    def _read_range(*, config_dir, vacuum_entity_id, start_iso, end_iso):
        seen["start"], seen["end"] = start_iso, end_iso
        seen["vacuum"] = vacuum_entity_id
        return samples

    monkeypatch.setattr(sc.pose_store, "read_range", _read_range)
    return seen


def test_trail_keeps_real_anchors_in_order(monkeypatch):
    """[SL-8] Oldest-first, and the anchor values pass through untouched."""
    _ring(monkeypatch, [
        {"anchor": [0.1, 0.1]},
        {"anchor": [0.2, 0.3]},
        {"anchor": [0.4, 0.5]},
    ])

    trail = sc._trail_from_ring("/config", "vacuum.ivy", _WHEN)

    assert trail == [[0.1, 0.1], [0.2, 0.3], [0.4, 0.5]]


def test_null_anchors_are_dropped_not_zeroed(monkeypatch):
    """[SL-8] A docked or held tick is a genuine None-run.

    Coercing it to a point would draw the trail to the map's origin corner — a route
    across the whole floor plan, in the artifact whose job is showing what happened.
    """
    _ring(monkeypatch, [
        {"anchor": [0.1, 0.1]},
        {"anchor": None},          # docked / held
        {},                        # a tick with no anchor key at all
        {"anchor": [0.4, 0.5]},
        "not even a dict",         # a corrupt ring line must not crash the capture
    ])

    trail = sc._trail_from_ring("/config", "vacuum.ivy", _WHEN)

    assert trail == [[0.1, 0.1], [0.4, 0.5]]
    assert None not in trail and [0, 0] not in trail


def test_the_window_asked_of_the_ring_is_the_one_passed_in(monkeypatch):
    """[SL-8] The ± window is a parameter, so a coarse brand can bank more history.

    Pinned on the ISO strings the ring actually receives: a window that is computed and
    then not used is the failure that looks exactly like a correctly empty ring.
    """
    seen = _ring(monkeypatch, [])

    sc._trail_from_ring("/config", "vacuum.ivy", _WHEN, 75)

    assert seen["start"] == "2026-08-09T11:58:45Z"   # -75s
    assert seen["end"] == "2026-08-09T12:01:15Z"     # +75s


def test_the_default_window_is_the_historical_thirty_seconds(monkeypatch):
    """[SL-8] A caller that passes nothing gets exactly the old behaviour."""
    seen = _ring(monkeypatch, [])

    sc._trail_from_ring("/config", "vacuum.ivy", _WHEN)

    assert seen["start"] == "2026-08-09T11:59:30Z"
    assert seen["end"] == "2026-08-09T12:00:30Z"


def test_an_unreadable_ring_costs_the_trail_not_the_capture(monkeypatch):
    """[SL-8] The ring is best-effort context; the dot and the room still render."""
    def _boom(**_kw):
        raise OSError("ring unreadable")

    monkeypatch.setattr(sc.pose_store, "read_range", _boom)

    assert sc._trail_from_ring("/config", "vacuum.ivy", _WHEN) == []


# ---------------------------------------------------------------------------
# the window comes from the adapter
# ---------------------------------------------------------------------------

def test_pose_cadence_is_read_from_the_adapter_declaration(monkeypatch):
    """[SL-9] The number is declared per brand, never assumed here."""
    monkeypatch.setattr(
        sc, "get_adapter_value",
        lambda vid, *path, **kw: 30.0 if path[-1] == "pose_refresh_s" else None,
    )

    assert sc.pose_refresh_seconds("vacuum.ivy") == 30.0


@pytest.mark.parametrize("declared", [None, "soon", 0, -1])
def test_a_brand_declaring_no_cadence_reports_none(monkeypatch, declared):
    """[SL-9] None is the honest answer, and the caller falls back to the floor.

    It must NOT resolve to some brand's number: a wrong cadence would size the window and
    pick the draw style for a brand it was never measured on.
    """
    monkeypatch.setattr(sc, "get_adapter_value", lambda vid, *path, **kw: declared)

    assert sc.pose_refresh_seconds("vacuum.mystery") is None


# ---------------------------------------------------------------------------
# durability of the write (C29)
# ---------------------------------------------------------------------------

def test_the_tmp_is_fsynced_before_the_rename(tmp_path, monkeypatch):
    """[SL-10] `os.replace` is rename-atomic but NOT durable.

    Without the fsync, a power loss between the write and the OS lazily flushing dirty
    pages leaves a ZERO-LENGTH PNG at the stable path an automation hardcodes -- after
    `stall.capture.written` already reported P. The ORDER is the whole claim: an fsync
    after the rename would not protect the tmp's contents, so the assertion is that the
    sync landed while the tmp was still the file being synced.
    """
    order: list[str] = []
    real_fsync = os.fsync
    real_replace = os.replace

    def _spy_fsync(fd):
        # Prove the sync is aimed at the tmp, not at some unrelated descriptor: its
        # size at sync time must already be the full payload.
        order.append(f"fsync:{os.fstat(fd).st_size}")
        return real_fsync(fd)

    def _spy_replace(src, dst):
        order.append("replace")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "fsync", _spy_fsync)
    monkeypatch.setattr(os, "replace", _spy_replace)

    path = str(tmp_path / "stall" / "12.png")
    sc._write_atomic(path, b"\x89PNG-payload")

    assert order == ["fsync:12", "replace"], (
        "the tmp must be fsynced -- with its full contents -- BEFORE the rename; "
        f"observed {order}"
    )
    assert (tmp_path / "stall" / "12.png").read_bytes() == b"\x89PNG-payload"


def test_a_failed_rename_does_not_strand_the_floor_plan(tmp_path, monkeypatch):
    """[SL-10] The tmp lives at a FIXED `<path>.tmp`, so a failure leaks a real picture.

    A rendered floor-plan of the user's home left beside the capture breaks the
    one-file-per-(vacuum, map) contract the module promises, and nothing ever reclaims
    it -- every subsequent failure just overwrites the same orphan.
    """
    real_replace = os.replace

    def _boom(src, dst):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "replace", _boom)

    path = str(tmp_path / "stall" / "12.png")
    with pytest.raises(OSError):
        sc._write_atomic(path, b"\x89PNG-payload")

    assert not os.path.exists(f"{path}.tmp"), (
        "a failed rename must not leave the rendered PNG at <path>.tmp"
    )
    assert not os.path.exists(path)

    # And the caller can retry cleanly once the disk frees up.
    monkeypatch.setattr(os, "replace", real_replace)
    sc._write_atomic(path, b"\x89PNG-payload")
    assert os.path.exists(path)

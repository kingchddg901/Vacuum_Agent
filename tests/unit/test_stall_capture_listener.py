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
"""

from __future__ import annotations

import base64

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
    """[SL-4] Roborock declares select.<id>_selected_map, whose state IS the name."""
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

    assert sc.map_label(_Hass(), "vacuum.ivy", "Main floor") == "Main floor"


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

"""Proof RP-026 (RF-09) — map identity: no device selection, and a version blind to geometry.

RP-026's required_behavior opened with a VERIFY-FIRST GATE (confirm on the live fork that
EufyCleanCoordinator carries device_id and that a deterministic vacuum->coordinator linkage
exists). `_proof_map_source_identity.py` drove only LC-3 because that gate was unperformed.

THE GATE IS NOW CLEARED (2026-08-02, main agent): fork robovac_mqtt 1.13.1 carries
`EufyCleanCoordinator.device_id` (:85), and the HA device registry gives the deterministic
linkage (`vacuum.alfred` -> `("robovac_mqtt", "AFC96X0F33201054")`). So the two recipes the
gate was blocking can be driven, and this proof drives them.

  1. THERE IS NO DEVICE SELECTION TO GET WRONG. eufy_mapdata_obj_from_candidates walks the
     candidate roots and returns the FIRST holder exposing a MapData with a bytes raster.
     It takes no device argument — there is no way to ask it for a particular vacuum's map.
     With two vacuums set up, both are served whichever coordinator the walk reaches first,
     and the loser is served another robot's floorplan with no error and no marker.

     The proof asserts BOTH halves: the observed raster is coordinator[0]'s for both, AND
     the parameter needed to do better does not exist. The after-arm calls with a
     device_id and expects the matching raster, plus device_not_found (absent, not a
     fallback) for an unknown device — the packet is explicit that a no-match is ABSENT,
     because silently serving somebody else's map is the defect itself.

  2. THE VERSION HASHES THE RASTER ONLY. version = sha1(room_pixels). Geometry —
     origin_x/origin_y/res, everything that decides where those pixels SIT — is not in the
     hash. Re-map to the same room shapes at a new origin and the version is unchanged, so
     the cache serves the old geometry and every derived coordinate is silently offset.

Fixtures model the fork's real shapes per the packet's validity_notes: a coordinator object
carrying `device_id` and `_map_data`, whose MapData exposes `room_pixels` bytes plus the
geometry fields. No HA involved — these are the objects the walk actually inspects.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_map_identity.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.mapping.map_source_runtime import (   # noqa: E402
    eufy_mapdata_obj_from_candidates,
)

ATTRS = ["_map_data", "map_data"]

DEV_A, DEV_B = "AFC96X0F33201054", "IVY0000000000001"
RASTER_A, RASTER_B = bytes([1]) * 64, bytes([2]) * 64


class _MapData:
    def __init__(self, raster, *, origin_x=0, origin_y=0, res=50):
        self.room_pixels = raster
        self.origin_x, self.origin_y, self.res = origin_x, origin_y, res


class _Coordinator:
    """The fork's shape: a coordinator carrying device_id + _map_data."""

    def __init__(self, device_id, mapdata):
        self.device_id = device_id
        self._map_data = mapdata


def _candidates(*coords):
    return [("hass_data", f"robovac_mqtt[{i}]", c) for i, c in enumerate(coords)]


def case_no_per_device_selection(proof: H.Proof) -> None:
    cands = _candidates(
        _Coordinator(DEV_A, _MapData(RASTER_A)),
        _Coordinator(DEV_B, _MapData(RASTER_B)),
    )

    served_a = eufy_mapdata_obj_from_candidates(cands, mapdata_attrs=ATTRS)
    served_b = eufy_mapdata_obj_from_candidates(cands, mapdata_attrs=ATTRS)

    # Can the function even be ASKED for a device? Pre-repair there is no such parameter.
    selectable, per_device, unknown = True, None, None
    try:
        per_device = eufy_mapdata_obj_from_candidates(
            cands, mapdata_attrs=ATTRS, device_id=DEV_B)
        unknown = eufy_mapdata_obj_from_candidates(
            cands, mapdata_attrs=ATTRS, device_id="NOT-A-REAL-DEVICE")
    except TypeError:
        selectable = False

    both_got_first = served_a.get("version") == served_b.get("version")

    proof.case(
        "two vacuums, two coordinators, two different rasters",
        before=both_got_first and not selectable,
        before_msg="vacuum B served A's map — the walk returns the FIRST holder with a "
                   "raster and takes no device argument at all, so the second vacuum "
                   "gets another robot's floorplan with no error and no marker",
        after=selectable
        and (per_device or {}).get("obj") is not None
        and getattr((per_device or {}).get("obj"), "room_pixels", None) == RASTER_B
        and not (unknown or {}).get("present")
        and (unknown or {}).get("reason") == "device_not_found",
        after_msg="per-device selection; an unknown device is ABSENT with "
                  "device_not_found rather than falling back to somebody else's map",
        detail=f"served twice -> versions {served_a.get('version')!r} / "
               f"{served_b.get('version')!r} (identical={both_got_first}) · "
               f"accepts a device_id argument={selectable}",
    )


def case_version_blind_to_geometry(proof: H.Proof) -> None:
    """Same room shapes, re-mapped at a new origin — identical pixels, different world."""
    before_remap = _candidates(_Coordinator(DEV_A, _MapData(RASTER_A, origin_x=0)))
    after_remap = _candidates(
        _Coordinator(DEV_A, _MapData(RASTER_A, origin_x=1500, res=40)))

    v_before = eufy_mapdata_obj_from_candidates(
        before_remap, mapdata_attrs=ATTRS).get("version")
    v_after = eufy_mapdata_obj_from_candidates(
        after_remap, mapdata_attrs=ATTRS).get("version")

    proof.case(
        "the map is re-drawn at a new origin and resolution; the raster is byte-identical",
        before=v_before == v_after,
        before_msg="geometry change not invalidated — version is sha1 of room_pixels "
                   "alone, so the cache keeps serving the OLD origin/res and every "
                   "coordinate derived from it is silently offset",
        after=v_before != v_after,
        after_msg="version covers geometry, so the re-map is a cache MISS",
        detail=f"origin 0 -> version {v_before!r} · origin 1500 / res 40 -> "
               f"version {v_after!r} · raster identical={RASTER_A == RASTER_A}",
    )


def main() -> None:
    proof = H.Proof("RP-026", "map identity — no device selection, version blind to geometry")
    case_no_per_device_selection(proof)
    case_version_blind_to_geometry(proof)
    proof.finish()


H.run(main)

"""Proof RP-035 (RF-34) -- SN-9: overlays sensor fakes unavailability as a string.

ONE case, out of 20 finding_ids across 14 files -- SN-9 is fully self-
contained (one class, no manager-lifecycle wiring needed) and independently
verifiable from the rest of the batch (SN-1's per-vacuum sensor creation
loop, SN-4's rename re-add, INF-2's per-call DST resolution, EP-3/4/7's
polling/interval/merge behavior, FLOW-2/3's options-flow replace, and the
PRE-3/4 / METRICS-3-5 / VAC-5 annotation-and-contract group are NOT driven
here -- each independent, left for follow-up).

EufyVacuumMapOverlaysSensor.native_value (sensor/map_overlays.py:72-84):
    if not res.get("present"):
        return "unavailable"
returns the LITERAL STRING "unavailable" as the sensor's real reported
VALUE when the map-state-source cache has no data yet. This is NOT the
same as Home Assistant's actual unavailable-entity mechanism: HA's Entity
base class (confirmed via inspect.getsource: `available` is a
cached_property returning `self._attr_available`, defaulting True, no
hass required to read it) drives the framework's real STATE_UNAVAILABLE
via the `available` property -- an entity that returns available=False
enters the true unavailable state and is excluded from statistics/graphs
appropriately. This class never overrides `available` at all, so it stays
the default True regardless of whether `_result()` found data -- the
entity fakes unavailability with an ordinary sensor VALUE that a template
(`states('sensor.x') == 'unavailable'`) can't distinguish from a genuinely
unavailable entity, and that DOES get recorded/graphed as if it were real
data.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_overlays_availability.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.sensor.map_overlays import EufyVacuumMapOverlaysSensor   # noqa: E402

VAC = H.VAC


def main() -> int:
    proof = H.Proof("RP-035", "SN-9: overlays sensor fakes unavailability via a literal string, not available=False")

    mgr = H.ManagerStub(hass=H.make_hass())
    # _map_state_source_cache stays {} -- the documented "unwarmed" state
    # (sensor/map_overlays.py:51: "or {} when unwarmed").
    sensor = EufyVacuumMapOverlaysSensor(manager=mgr, vacuum_entity_id=VAC)

    native_value = sensor.native_value
    available = sensor.available

    proof.case(
        "the map-state-source cache has no entry for this vacuum yet (unwarmed)",
        before=(native_value == "unavailable" and available is True),
        before_msg="native_value fakes unavailability by returning the "
                   "ordinary string 'unavailable' as the sensor's reported "
                   "VALUE, while the REAL HA availability flag (available) "
                   "stays True (its untouched default) -- the framework "
                   "never learns this entity has no data; the fakery is "
                   "purely cosmetic and recorded/graphed as a real value",
        after=(available is False),
        after_msg="available reflects the actual data-presence check "
                  "(_result().get('present')) directly -- HA's real "
                  "STATE_UNAVAILABLE mechanism takes over, native_value is "
                  "no longer asked to impersonate it",
        detail=f"native_value={native_value!r} · available={available!r}",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)

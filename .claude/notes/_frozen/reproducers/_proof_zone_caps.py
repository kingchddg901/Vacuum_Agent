"""Proof RP-022 (RF-23) — declared caps on every branch; Q12 zone repeats.

Four cases (of ten finding_ids -- SNAP-4/snapshot-parity and the card halves
of ZONE-C-8/ZONE-5 are NOT driven here; time-boxed, left for a follow-up
pass alongside the card work itself).

dispatch_zone_clean (dispatch/manager.py:88-247) branches on
cfg.get("zone_coords") == "device_mm": the device_mm branch (Roborock)
converts to world mm and enforces zone_min_area_m2/zone_max_area_m2 PLUS a
repeat cap (zone_passes_max/passes_max, clamped); the else branch (Eufy,
normalized 0-1 rects shipped verbatim) enforces zone_min_side_m/
zone_max_side_m but has NO repeat clamp at all -- clean_times ships exactly
as given. Each per-zone bound is checked in exactly one branch regardless of
which the adapter actually declares.

  Q12 -- Eufy clean_times=5 ships to the wire verbatim (line 236:
    payload = {"zones": zones, "clean_times": int(clean_times)} -- no clamp).
  item 2 -- a zone_max_area_m2 bound declared on a non-device_mm adapter is
    never checked (area bounds only exist in the device_mm branch); a
    zone-side violation that WOULD be caught on the else branch is silently
    unenforced there too when unreadable dims are involved (folded into the
    unreadable-dims case below instead, to avoid two near-identical cases).
  ZONE-4 -- the else branch's side-bound check is entirely skipped (not
    refused) when the live map's dims can't be read (`if _w and _h:` --
    no else clause at all), while the device_mm branch explicitly REFUSES
    when no live map is available (line 151-155) for the exact same
    "can't validate the geometry" situation.
  ZONE-2 -- dispatch_zone_clean never reads supports_zone_clean anywhere in
    its body (grepped the full function) -- a brand that declares it
    unsupported still dispatches.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_zone_caps.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config   # noqa: E402
from custom_components.eufy_vacuum.dispatch.manager import DispatchManager   # noqa: E402

VAC = H.VAC
MAP = "1"


def main() -> int:
    proof = H.Proof("RP-022", "declared caps on every branch; Q12 zone repeats")
    import asyncio

    # -------------------------------------------------------------------
    # Case 1 (Q12): Eufy clean_times ships verbatim, no repeat cap.
    # -------------------------------------------------------------------
    hass = H.make_hass()
    register_adapter_config(VAC, {
        "adapter_id": "eufy", "source": "code",
        "dispatch": {"zone_command": "zone_clean", "service_domain": "vacuum",
                     "service_name": "send_command"},
        "capabilities": {},
    })
    mgr = H.ManagerStub(hass=hass)
    dispatch = DispatchManager(manager=mgr)

    asyncio.run(dispatch.dispatch_zone_clean(
        vacuum_entity_id=VAC, zones=[[0.1, 0.1, 0.5, 0.5]], clean_times=5,
    ))
    sent = hass.services.calls[-1]["data"]
    sent_clean_times = sent.get("params", {}).get("clean_times")

    proof.case(
        "Eufy zone clean requested with clean_times=5",
        before=sent_clean_times == 5,
        before_msg="clean_times ships to the wire exactly as given -- three "
                   "schema comments claim dispatch enforces a ceiling; none "
                   "does",
        after=sent_clean_times == 1,
        after_msg="Q12: Eufy zone repeats are unsupported -- normalized to 1 "
                  "with a warning, not clamped to some other number",
        detail=f"wire clean_times={sent_clean_times}",
    )

    # -------------------------------------------------------------------
    # Case 2: a declared area bound is never checked on the non-device_mm
    # (Eufy) branch -- only the device_mm branch reads zone_max_area_m2.
    # -------------------------------------------------------------------
    hass2 = H.make_hass()
    register_adapter_config(VAC, {
        "adapter_id": "eufy", "source": "code",
        "dispatch": {"zone_command": "zone_clean", "service_domain": "vacuum",
                     "service_name": "send_command"},
        # a max area bound IS declared -- just never consulted on this branch.
        "capabilities": {"zone_max_area_m2": 0.01},
    })
    mgr2 = H.ManagerStub(hass=hass2)
    dispatch2 = DispatchManager(manager=mgr2)

    raised = None
    try:
        # a large zone (0.9x0.9 of the image) that would massively exceed
        # a 0.01 m^2 cap under ANY reasonable map scale.
        asyncio.run(dispatch2.dispatch_zone_clean(
            vacuum_entity_id=VAC, zones=[[0.0, 0.0, 0.9, 0.9]], clean_times=1,
        ))
    except ValueError as exc:
        raised = str(exc)

    proof.case(
        "a declared zone_max_area_m2 bound on the non-device_mm (Eufy) branch",
        before=raised is None,
        before_msg="dispatch proceeds without error -- zone_max_area_m2 is "
                   "only ever read inside the device_mm branch (Roborock); "
                   "this branch never resolves it regardless of declaration",
        after=raised is not None and "too large" in (raised or ""),
        after_msg="cap resolution is hoisted above the coordinate-space "
                  "branch and enforced on every branch -- the same "
                  "declared bound now refuses here too",
        detail=f"raised={raised!r}",
    )

    # -------------------------------------------------------------------
    # Case 3 (ZONE-4): unreadable dims silently skip the check (Eufy),
    # vs. the device_mm branch's explicit refusal for the same situation.
    # -------------------------------------------------------------------
    hass3 = H.make_hass()
    register_adapter_config(VAC, {
        "adapter_id": "eufy", "source": "code",
        "dispatch": {"zone_command": "zone_clean", "service_domain": "vacuum",
                     "service_name": "send_command"},
        "capabilities": {"zone_min_side_m": 100.0},   # an enormous, easily-violated bound
    })
    mgr3 = H.ManagerStub(hass=hass3)
    mgr3.async_get_map_data_dict = H.async_noop({})   # unreadable dims -> width/height absent
    dispatch3 = DispatchManager(manager=mgr3)

    raised3 = None
    try:
        asyncio.run(dispatch3.dispatch_zone_clean(
            vacuum_entity_id=VAC, zones=[[0.1, 0.1, 0.2, 0.2]], clean_times=1,
        ))
    except ValueError as exc:
        raised3 = str(exc)

    proof.case(
        "live map dims unreadable, with a side bound declared (easily violated)",
        before=raised3 is None,
        before_msg="the side-bound check is silently skipped when width/"
                   "height can't be read (`if _w and _h:` with no else) -- "
                   "the zone dispatches unchecked",
        after=raised3 is not None,
        after_msg="parity with the device_mm branch's own refusal for the "
                  "identical 'can't validate the geometry' situation",
        detail=f"raised={raised3!r}",
    )

    # -------------------------------------------------------------------
    # Case 4 (ZONE-2): supports_zone_clean is never consulted.
    # -------------------------------------------------------------------
    hass4 = H.make_hass()
    register_adapter_config(VAC, {
        "adapter_id": "eufy", "source": "code",
        "dispatch": {"zone_command": "zone_clean", "service_domain": "vacuum",
                     "service_name": "send_command"},
        "capabilities": {"supports_zone_clean": False},
    })
    mgr4 = H.ManagerStub(hass=hass4)
    dispatch4 = DispatchManager(manager=mgr4)

    raised4 = None
    try:
        asyncio.run(dispatch4.dispatch_zone_clean(
            vacuum_entity_id=VAC, zones=[[0.1, 0.1, 0.5, 0.5]], clean_times=1,
        ))
    except ValueError as exc:
        raised4 = str(exc)

    proof.case(
        "adapter declares supports_zone_clean=False",
        before=raised4 is None,
        before_msg="dispatch_zone_clean never reads supports_zone_clean -- "
                   "only the card consults it, so a direct/automation call "
                   "still dispatches",
        after=raised4 is not None,
        after_msg="dispatch_zone_clean consults supports_zone_clean and "
                  "refuses when false",
        detail=f"raised={raised4!r}",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)

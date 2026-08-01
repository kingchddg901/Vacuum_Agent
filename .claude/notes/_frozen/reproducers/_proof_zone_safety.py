"""Proof RP-029 (RF-25/RF-13 cousins) — zone & custom-layout safety.

Two cases (of twelve finding_ids -- map_version invalidation (ZONE-C-3),
room_number_source precedence (CUSTOM-4), the rasterize/trace round-trip
(POLYGO-1), multi-loop dropping (POLYGO-4), capability/per-primitive
failure honesty (POLYGO-2/8), non-clean-kind refusal (ZONE-C-7), and
delete-honesty (IMAGE--7) are NOT driven here; time-boxed, left for a
follow-up pass).

  ZONE-C-1 -- _handle_clean_saved_zone's active-map guard
    (mapping_services.py:2621): `if active_map_id is not None and
    str(active_map_id) != str(map_id): refuse`. When active_map_id IS None
    (the adapter's active_map entity is unreadable/blank -- indeterminate,
    not "no mismatch"), the guard's own condition is false and the whole
    check is skipped -- the zone dispatches on an indeterminate active map,
    exactly the permissive-guard shape RF-13's rule (indeterminate != match)
    already closed for blocker rules (RP-008) and is not yet applied here.
  POLYGO-3 -- _apply_segment_adjustments (mapping_services.py:756-786)
    returns ALIASED references (not copies) for any segment with no stored
    adjustment (`result.append(seg)`, the same dict object, at three
    separate return points). _handle_get_map_segments then mutates every
    segment in that list IN PLACE (`seg["polygon_pct"] = ...` at line 1243,
    `seg["room_id"] = ...` at line 1260) to enrich the RESPONSE -- which,
    via the aliasing, writes room_id and polygon_pct directly into the
    PERSISTED map_bucket["image_segments"]["segments"] entries. A later
    read (or the next analyze_map_image, which reads these as the prior
    segments) sees a room_id the analysis itself never produced.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_zone_safety.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.const import DOMAIN, DATA_RUNTIME   # noqa: E402
from custom_components.eufy_vacuum.mapping.mapping_services import (   # noqa: E402
    _handle_clean_saved_zone,
    _handle_get_map_segments,
)
from custom_components.eufy_vacuum.maps.map_manager import ensure_map_bucket   # noqa: E402

VAC = H.VAC
MAP = "1"


def main() -> int:
    proof = H.Proof("RP-029", "zone & custom-layout safety")
    import asyncio

    # -------------------------------------------------------------------
    # Case 1 (ZONE-C-1): blank/indeterminate active map dispatches anyway.
    # -------------------------------------------------------------------
    hass = H.make_hass()
    mgr = H.ManagerStub(hass=hass)
    mgr.async_save = H.async_noop()
    dispatched = []
    mgr.dispatch_zone_clean = H.async_noop({"status": "dispatched"})

    async def _capture_dispatch(**kw):
        dispatched.append(kw)
        return {"status": "dispatched"}
    mgr.dispatch_zone_clean = _capture_dispatch
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = mgr

    bucket = ensure_map_bucket(data=mgr.data, vacuum_entity_id=VAC, map_id=MAP)
    bucket["saved_zones"] = {"z1": {
        "id": "z1", "name": "Kitchen Corner",
        "geometry": [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]],
    }}
    # deliberately NO adapter registered -- get_active_map_id degrades to
    # None (indeterminate), not a specific (mis)matching map.

    class _Call:
        data = {"vacuum_entity_id": VAC, "map_id": MAP, "zone_id": "z1"}

    result = asyncio.run(_handle_clean_saved_zone(hass, _Call()))

    proof.case(
        "the active map is indeterminate (no adapter/active_map signal readable)",
        before=result.get("cleaned") is True and len(dispatched) == 1,
        before_msg="active_map_id resolves to None, the guard's own "
                   "condition requires it to be NOT None to refuse, so the "
                   "check is skipped entirely -- the zone dispatches with "
                   "no evidence it's even on the right map",
        after=result.get("cleaned") is False and len(dispatched) == 0,
        after_msg="indeterminate != match -- an unreadable active-map "
                  "signal refuses the clean, the same rule RP-008 already "
                  "applied to blocker rules",
        detail=f"result={result} · dispatch_zone_clean calls={len(dispatched)}",
    )

    # -------------------------------------------------------------------
    # Case 2 (POLYGO-3): get_map_segments mutates PERSISTED segment dicts.
    # -------------------------------------------------------------------
    hass2 = H.make_hass()
    mgr2 = H.ManagerStub(hass=hass2)
    hass2.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = mgr2

    bucket2 = ensure_map_bucket(data=mgr2.data, vacuum_entity_id=VAC, map_id=MAP)
    stored_segment = {"segment_id": "1", "polygon_pixel": [[0, 0], [10, 0], [10, 10]]}
    bucket2["image_segments"] = {"segments": [stored_segment], "image": {"width": 100, "height": 100}}
    bucket2["image_segment_adjustments"] = {}   # no adjustment for segment "1" -> aliased
    bucket2["segment_room_links"] = {"1": 42}

    class _Call2:
        data = {"vacuum_entity_id": VAC, "map_id": MAP}

    asyncio.run(_handle_get_map_segments(hass2, _Call2()))
    persisted_after = bucket2["image_segments"]["segments"][0]

    proof.case(
        "get_map_segments enriches its response for a segment with no stored adjustment",
        before="room_id" in persisted_after,
        before_msg="the PERSISTED segment dict (the same object the response "
                   "was built from, via _apply_segment_adjustments' aliased "
                   "pass-through) now carries room_id='42' -- a field the "
                   "stored analysis never produced, written by a READ endpoint",
        after="room_id" not in persisted_after,
        after_msg="_apply_segment_adjustments returns copies; the caller's "
                  "enrichment writes only into the response, never touching "
                  "the stored analysis",
        detail=f"persisted segment after a read-only call={persisted_after} "
               f"(is the SAME object passed in: {persisted_after is stored_segment})",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)

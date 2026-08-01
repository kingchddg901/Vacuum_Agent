"""Proof RP-028 (RF-15) — mapping services: no phantom buckets, addressed writes.

Two cases (of eleven finding_ids -- the require_managed_vacuum sweep across
queue/snapshots/errors/dock/themes (item 3) and the filename sanitizer
(IMAGE--5) are NOT driven here; time-boxed, left for a follow-up pass. Both
driven cases exercise the SAME root cause -- ensure_map_bucket's
unconditional setdefault -- through real, unmodified service handlers, not
a hand-rolled stand-in).

  SERVIC-1 -- ensure_map_bucket (maps/map_manager.py:10-28) has no concept
    of "does this map/vacuum actually exist" -- it setdefaults a durable
    bucket for ANY (vacuum_entity_id, map_id) pair. Driven through the real
    _handle_create_saved_zone (mapping_services.py:2488), which calls it
    directly with no prior existence check: a create_saved_zone call for a
    vacuum/map_id that has never been discovered reports saved:true and
    persists a durable bucket under a phantom map_id.
  CUSTOM-1 -- _handle_set_custom_segments (mapping_services.py:1657) has no
    layout_id parameter at all (grepped call.data accesses: vacuum_entity_id,
    map_id, segments, backdrop_width, backdrop_height -- never layout_id).
    It resolves whatever _ensure_default_layout returns and REPLACES that
    layout's entire custom_segments wholesale -- a destructive REPLACE-ALL
    with no way for the caller to name which layout it's targeting.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_phantom_buckets.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.const import DOMAIN, DATA_RUNTIME   # noqa: E402
from custom_components.eufy_vacuum.mapping.mapping_services import (   # noqa: E402
    _handle_create_saved_zone,
    _handle_set_custom_segments,
)

VAC = H.VAC


def main() -> int:
    proof = H.Proof("RP-028", "mapping services: no phantom buckets, addressed writes")
    import asyncio

    # -------------------------------------------------------------------
    # Case 1 (SERVIC-1): a write against an unknown map mints a phantom bucket.
    # -------------------------------------------------------------------
    hass = H.make_hass()
    mgr = H.ManagerStub(hass=hass)
    mgr.async_save = H.async_noop()
    mgr.async_get_map_data_dict = H.async_noop(None)
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = mgr

    class _Call:
        data = {
            "vacuum_entity_id": VAC, "map_id": "phantom-map-9999",
            "name": "Bogus Zone", "geometry": [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]],
        }

    result = asyncio.run(_handle_create_saved_zone(hass, _Call()))
    bucket_minted = "phantom-map-9999" in mgr.data.get("maps", {}).get(VAC, {})

    proof.case(
        "create_saved_zone against a map_id that was never discovered",
        before=result.get("saved") is True and bucket_minted,
        before_msg="ensure_map_bucket mints a durable bucket for ANY map_id "
                   "-- the write reports saved:true against a map that does "
                   "not exist, and the phantom bucket persists",
        after=result.get("saved") is False and result.get("reason") == "map_not_found",
        after_msg="require_map_bucket refuses with {reason: map_not_found, "
                  "known_maps: [...]} instead of minting a bucket for an "
                  "unknown map",
        detail=f"result={result} · phantom bucket persisted={bucket_minted}",
    )

    # -------------------------------------------------------------------
    # Case 2 (CUSTOM-1): set_custom_segments has no layout_id parameter.
    # -------------------------------------------------------------------
    hass2 = H.make_hass()
    mgr2 = H.ManagerStub(hass=hass2)
    mgr2.async_save = H.async_noop()
    hass2.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = mgr2

    class _Call2:
        data = {
            "vacuum_entity_id": VAC, "map_id": "1", "segments": [],
            "backdrop_width": 100, "backdrop_height": 100,
        }

    result2 = asyncio.run(_handle_set_custom_segments(hass2, _Call2()))

    proof.case(
        "set_custom_segments called with no layout_id at all",
        before=result2.get("saved") is True,
        before_msg="no layout_id parameter exists in the schema or the "
                   "handler -- a destructive REPLACE-ALL proceeds against "
                   "whichever layout _ensure_default_layout happens to "
                   "resolve, with no way for the caller to name a target",
        after=result2.get("saved") is False,
        after_msg="set_custom_segments requires layout_id -- the "
                  "active-layout fallback is refused for this destructive "
                  "replace, mirroring upload's own contract",
        detail=f"result={result2}",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)

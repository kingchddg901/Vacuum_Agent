"""Service-call room-source refresh + flatten shim.

Two discovery *sources* exist in the framework:

  - ``entity_attribute`` (default, Eufy) — the room list is a live attribute on
    an HA entity. ``rooms/room_discovery.py`` reads it synchronously; nothing to
    refresh because the attribute is always current.

  - ``service_response`` (Roborock) — the room list only exists in the RESPONSE
    of a service call (``roborock.get_maps``), never as an entity attribute.
    Service calls are async; the sync discovery path (and its many callers:
    drift, onboarding) cannot make one. So an async refresher calls the service
    at the async boundaries (the discover service handler + the auto-discovery
    listener), flattens the response into the same list-of-dicts shape an
    attribute would have carried, and caches it. The sync discovery path then
    reads the cache instead of an attribute — one branch, everything downstream
    (slug, dedupe, int-coerce) unchanged.

The flatten shim normalizes ``get_maps``'s ``{segment_id_str: name}`` room
mapping into ``[{<room_id_key>: id_str, <room_name_key>: name}, ...]`` per map,
keyed by the map NAME (which is what ``entities.active_map`` — Roborock's
``select.{id}_selected_map`` — reports, so the sync path's resolved active-map
id lines up with a cache key).

Public surface:
    async_refresh_room_source(hass, vacuum_entity_id) -> dict[str, Any]   (async)
    get_cached_room_source(hass, vacuum_entity_id) -> dict[str, list[dict]]
    get_cached_room_source_with_age(...)
    set_cached_room_source(hass, vacuum_entity_id, per_map) -> None
    invalidate_room_source_cache(...)
    select_segments_for_map(...)
    flatten_maps_response(response, *, discovery, vacuum_entity_id=..., active_map_id=...)
        -> dict[str, list[dict]]  (pure)

⚠ CORRECTED 2026-08-24 (R5), in two ways, and this is the FIRST thing a caller reads.

RETURN TYPE. `async_refresh_room_source` was listed `-> None`. It returns a dict with
seven distinct {ok, reason, refreshed_at} exits, documented on the function itself —
that WAS the RP-007/SRC-1 fix, whose whole point was that it stopped returning None, and
the stale claim sat at the top of the very file that fixed it. `dispatch/manager.py`
depends on the dict (`refresh_result.get("ok")`), so a caller who believed this header
and discarded the result would silently drop the outcome, or read a returned value as a
bug.

MEMBERSHIP. Three public functions were missing entirely —
`get_cached_room_source_with_age`, `invalidate_room_source_cache` and
`select_segments_for_map` — all defined here and all imported by other modules. A
"public surface" list that omits a third of the surface sends a reader looking for a
seam that is already there. `flatten_maps_response`'s listed signature also dropped its
two keyword params.
"""

# System invariants that bind in this file. Declared and explained elsewhere
# (docs/dev/00b-invariants.md); `scripts/doc_anchor.py --show <TOKEN>` from here.
# The findings under each are the FAILURES THAT PRODUCED the rule -- history, with
# the packet that OWNS them. They are not a to-do list; see OPEN-FIX-CHECKLIST.
#
# A packet id here is the ledger's ATTRIBUTION, not a verification that the fix
# landed in THIS file. Measured 2026-08-18 (.claude/notes/_audit_closure_claims.py):
# 35 of 60 claims name a packet whose commits -- full git footprint, not just the
# ledger's list -- never touched the file the claim sits in. Two were then read and
# both were still LIVE: DQ-Q-7 (queue_engine) and A5-PP-RP-8 (this pattern, in both
# copies). These blocks were written 2026-08-17 by transcribing the ledger, so they
# inherited its mis-attributions into source -- where prose at the site reads as
# authority. Verify before citing one as closed.
#
# THE REVERSE TRAP IS REAL TOO, and it cost R18. This block marks a closed
# finding by appending "(closed <packet>)"; so with some entries marked and
# others not, the UNMARKED ones read as still live -- in a file that visibly
# fixed them. Absence of a marker is not evidence of an open finding. A4-SRC-1,
# A4-SRC-3 and A4-SRC-4 sat unmarked here until 2026-08-24 and were stamped only
# after reading the code in THIS file, not after re-reading the ledger.
#
#   IN2QDNB3  `learning/history_store.py#IN2QDNB3`
#       A4-SRC-2 (closed RP-006): set_cached_room_source is called unconditionally on every successful service call,
#              so a response the flatten shim does not recognise (or an empty maps list) silently
#   INT79PB7  `core/manager.py#INT79PB7`
#       A4-SRC-5 (closed RP-007): The room-source cache is never invalidated — not on config-entry unload/reload, not
#              on map switch, not when a vacuum is unmanaged — and it keeps hass.data[DOMAIN] alive
#   INJBNQ2Q  `dispatch/manager.py#INJBNQ2Q`
#       A4-SRC-1 (closed RP-007; stamped 2026-08-24, R18): async_refresh_room_source RETURNED None on
#              success AND on every failure/skip path, and the cache carried no freshness stamp — dispatch
#              could not tell a fresh live snapshot from an arbitrarily old one, and rewrote the wire
#              payload with stale segment ids while believing it re-resolved live.
#              NOW, in this file: `async_refresh_room_source` returns the seven-exit
#              {ok, reason, refreshed_at} dict documented on the function, and
#              `set_cached_room_source` stamps every entry with `refreshed_at` + `refreshed_mono`.
#       A4-SRC-3 (closed RP-007; stamped 2026-08-24, R18): flatten_maps_response KEYED the cache by map
#              NAME with last-writer-wins and no collision detection; a collapsed cache chained into
#              room_discovery's single-map fallback and served one map's segment ids for a different
#              map_id.
#              NOW, in this file: `flatten_maps_response` detects a duplicate map name, suffixes the
#              second key with `#flag<n>`/`#idx<n>`, and logs a WARNING naming both.
#       A4-SRC-4 (closed RP-007; stamped 2026-08-24, R18): there WAS no in-flight coalescing or lock on the
#              refresh: triggers spawned unbounded concurrent get_maps cloud calls, and an older response
#              landing last became the resident cached snapshot — including one that started before a map
#              switch and landed after it.
#              NOW, in this file: `_INFLIGHT` coalesces concurrent callers onto one task, and the
#              `_GENERATION` commit guard discards a response whose generation was superseded while it
#              awaited (that is the `superseded_by_newer_refresh` exit).


from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotSupported

from ..adapters.registry import get_adapter_config
from ..const import DOMAIN
from ..timestamp_utils import utc_now_iso

_LOGGER = logging.getLogger(__name__)

#: hass.data[DOMAIN] slot holding the flattened per-vacuum room source cache.
#: Entry shape (RP-007): {"per_map": {map_name: [rooms]}, "refreshed_at": iso,
#: "refreshed_mono": float} — the ONLY shape any live entry can have.
#: ⚠ was: "Legacy raw per_map dicts are still readable" (corrected 2026-08-24,
#: RM8). True of the reader, but it reads as "such entries exist", and none can:
#: this cache lives only in hass.data, which dies with the process, and its sole
#: writer `set_cached_room_source` always stamps. There is no upgrade path an
#: unstamped entry could survive, so the legacy branch in
#: `get_cached_room_source_with_age` is unreachable in production.
DATA_ROOM_SOURCE_CACHE = "room_source_cache"

#: RP-007 step 7 (GATE4 Q16 variant a): how old a cached room source may be for
#: dispatch to trust it when a live refresh FAILS. Operational constant, not
#: empirical tuning — the intent is "recent enough that a vendor-app re-segment
#: in the gap is unlikely", not a measured device property.
REFRESH_TTL_SECONDS = 15 * 60

#: RP-007 step 3 (SRC-4): in-flight refresh coalescing + a monotonic commit
#: generation so a slow stale response can never replace a newer committed one.
_INFLIGHT: dict[str, asyncio.Task] = {}
_GENERATION: dict[str, int] = {}

#: Discovery source kinds — WHERE the room list comes from.
SOURCE_ENTITY_ATTRIBUTE = "entity_attribute"
SOURCE_SERVICE_RESPONSE = "service_response"

#: Discovery list shapes — WHAT the room list looks like, declared independently
#: of the source. These were conflated until 2026-08-07: the attribute source
#: assumed a flat list and the service source assumed per-map keying, so the
#: diagonal — a per-map MAPPING delivered as a live ATTRIBUTE — could not be
#: expressed at all, and a brand shaped that way discovered zero rooms.
SHAPE_FLAT_LIST = "flat_list"
SHAPE_PER_MAP_MAPPING = "per_map_mapping"


def select_segments_for_map(
    per_map: dict[str, Any] | None,
    resolved_map_id: str,
) -> list[Any] | None:
    """Pick one map's room list out of a {map_name: [rooms]} mapping.

    Shared by both discovery sources so the selection rule cannot drift between
    them — the per-map service response and a per-map entity attribute are the
    same question asked of different transports.

    The single-map fallback is deliberate and narrow: a brand with exactly one
    map whose active map was genuinely UNRESOLVABLE ("unknown") gets that one
    map rather than discovering nothing. An explicit, resolved map id that does
    not match a key is NEVER served another map's rooms relabelled with the
    requested id — that substitution is the RP-019/ID-2 bug this guards, and it
    is why the fallback checks ``resolved_map_id == "unknown"`` rather than
    simply falling back whenever the lookup misses.
    """
    if not isinstance(per_map, dict):
        return None
    segments = per_map.get(str(resolved_map_id))
    if segments is None and len(per_map) == 1 and resolved_map_id == "unknown":
        segments = next(iter(per_map.values()))
    return segments if isinstance(segments, list) else None


# ---------------------------------------------------------------------------
# anchor: BN9RY7DZ
# Cache accessors
# ---------------------------------------------------------------------------

def get_cached_room_source(
    hass: HomeAssistant,
    vacuum_entity_id: str,
) -> dict[str, list[dict[str, Any]]]:
    """Return the cached per-map flattened room source for one vacuum.

    Returns an empty dict when nothing has been refreshed yet (the sync
    discovery path then degrades to an empty room list, same as a missing
    attribute).
    """
    return get_cached_room_source_with_age(hass, vacuum_entity_id)[0]


def get_cached_room_source_with_age(
    hass: HomeAssistant,
    vacuum_entity_id: str,
) -> tuple[dict[str, list[dict[str, Any]]], float | None]:
    """Return (per_map, age_seconds) for one vacuum's cached room source.

    age is None when nothing has been cached — callers must treat None as "age
    unknown", i.e. NOT fresh.

    ⚠ was: "or when the entry predates the RP-007 freshness stamping (a legacy
    raw dict)" (corrected 2026-08-24, RM8). That case cannot arise in
    production, and stating it sent readers looking for a migration that does
    not exist: the cache is hass.data-only so it does not survive a restart, and
    `set_cached_room_source` — its only writer — always stamps. The unstamped
    branch below is defence against a hand-poked hass.data, nothing more.

    ⚠ And its discriminator is `"per_map" in value`: a KEY test, not a shape
    test. A raw per_map dict carrying a map literally named `per_map` would take
    the STAMPED branch, and because that map's value is a list of rooms rather
    than a dict the function would return an EMPTY per_map — every map's rooms
    dropped, not just the colliding one. Unreachable for the reason above, but
    do not reuse this discriminator anywhere a raw mapping can arrive.
    """
    cache = hass.data.get(DOMAIN, {}).get(DATA_ROOM_SOURCE_CACHE, {})
    value = cache.get(vacuum_entity_id)
    if isinstance(value, dict) and "per_map" in value:
        per_map = value.get("per_map")
        mono = value.get("refreshed_mono")
        age = (time.monotonic() - mono) if isinstance(mono, (int, float)) else None
        return (per_map if isinstance(per_map, dict) else {}, age)
    # legacy shape: the raw per_map dict, unstamped
    return (value if isinstance(value, dict) else {}, None)


def set_cached_room_source(
    hass: HomeAssistant,
    vacuum_entity_id: str,
    per_map: dict[str, list[dict[str, Any]]],
) -> None:
    """Store the flattened per-map room source for one vacuum (freshness-stamped)."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    cache = domain_data.setdefault(DATA_ROOM_SOURCE_CACHE, {})
    cache[vacuum_entity_id] = {
        "per_map": per_map,
        "refreshed_at": utc_now_iso(),
        "refreshed_mono": time.monotonic(),
    }


def invalidate_room_source_cache(
    hass: HomeAssistant,
    vacuum_entity_id: str | None = None,
) -> None:
    """Drop cached room sources (RP-007 step 4 / SRC-5): one vacuum's entry, or
    all of them on entry unload — a reloaded entry must not serve the previous
    life's cache as fresh."""
    cache = hass.data.get(DOMAIN, {}).get(DATA_ROOM_SOURCE_CACHE)
    if not isinstance(cache, dict):
        return
    if vacuum_entity_id is None:
        cache.clear()
    else:
        cache.pop(vacuum_entity_id, None)


# ---------------------------------------------------------------------------
# anchor: BNAJ69WK
# Flatten shim (pure — no hass)
# ---------------------------------------------------------------------------

def _extract_maps_list(
    response: Any,
    *,
    vacuum_entity_id: str | None = None,
) -> list[Any]:
    """Pull the ``maps`` list out of a get_maps ServiceResponse.

    Tolerates the shapes a ``return_response=True`` service call can produce:
      - ``{"maps": [...]}``                       (handler returns the dict directly)
      - ``{"<entity_id>": {"maps": [...]}}``      (response keyed by target entity)
      - ``[ {...}, ... ]``                        (handler returns the list bare)
    Returns an empty list for anything unrecognized.
    """
    if isinstance(response, list):
        return response
    if not isinstance(response, dict):
        return []

    # Direct {"maps": [...]}.
    maps = response.get("maps")
    if isinstance(maps, list):
        return maps

    # Per-entity wrapper: prefer the targeted entity, else the first dict value
    # that carries a "maps" list.
    if vacuum_entity_id and isinstance(response.get(vacuum_entity_id), dict):
        inner = response[vacuum_entity_id].get("maps")
        if isinstance(inner, list):
            return inner
    for value in response.values():
        if isinstance(value, dict) and isinstance(value.get("maps"), list):
            return value["maps"]

    return []


def _active_map_id_from_config(
    hass: HomeAssistant,
    config: dict[str, Any],
    vacuum_entity_id: str,
) -> str | None:
    """Return the adapter-declared active map value if it is currently valid."""
    active_map_entity = (config.get("entities") or {}).get("active_map")
    if not active_map_entity:
        return None

    state = hass.states.get(active_map_entity)
    if state is None:
        return None

    value = str(state.state).strip()
    if value in {"", "unknown", "unavailable", "none", "None"}:
        return None

    return value


def flatten_maps_response(
    response: Any,
    *,
    discovery: dict[str, Any],
    vacuum_entity_id: str | None = None,
    active_map_id: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Flatten a get_maps response into per-map normalized room lists.

    Each map's ``rooms`` value is a ``{segment_id_str: name}`` mapping; this
    rewrites it into a list of ``{<room_id_key>: id, <room_name_key>: name}``
    dicts — exactly the list-of-dicts shape the attribute-source discovery path
    already iterates. Map keys are the map NAME when present; when HA's Roborock
    response omits the name there are THREE fallbacks, tried in order — the
    active-map select value (single-map responses ONLY), then ``f"Map {flag}"``,
    then ``f"Map {index}"``.

    The third was documented nowhere at all until 2026-08-24 (R20/RM13) and is
    the one to know about: it is POSITIONAL, so it moves if the response
    reorders and it matches no active-map select value — a map keyed that way is
    effectively undiscoverable rather than merely unnamed. The comment at the
    fallback itself says why the single-map restriction on the first one is
    deliberate.

    Defensive against an already-list ``rooms`` value (returned as-is) and skips
    malformed entries. ``room_id_key``/``room_name_key`` default to the Roborock
    shape but honor the adapter's discovery config.
    """
    rooms_key = discovery.get("maps_rooms_key", "rooms")
    map_name_key = discovery.get("map_name_key", "name")
    room_id_key = discovery.get("room_id_key", "segment_id")
    room_name_key = discovery.get("room_name_key", "name")

    maps = _extract_maps_list(response, vacuum_entity_id=vacuum_entity_id)
    out: dict[str, list[dict[str, Any]]] = {}

    active_map_id = str(active_map_id).strip() if active_map_id else None

    for index, map_entry in enumerate(maps):
        if not isinstance(map_entry, dict):
            continue
        map_name = str(map_entry.get(map_name_key, "")).strip()
        if not map_name:
            # HA's Roborock integration can return an unnamed map while the
            # active-map select reports a synthetic name such as "Map 0".
            # Keep the cache key aligned with the select so discovery can find
            # the rooms it just refreshed.
            #
            # Three fallbacks, in order — and the CONDITIONS matter more than the
            # values (corrected 2026-08-24, R20/RM13):
            #
            #   1. the active-map value, but ONLY when this response carries
            #      exactly ONE map. That restriction is the deliberate part and
            #      was the part stated nowhere: with N maps there is no way to
            #      tell WHICH one the select's name belongs to, and guessing
            #      would file another map's segment ids under the active map's
            #      name.
            #   2. Roborock's numeric `flag`, as the same "Map <flag>" string HA
            #      shows. ⚠ was: "If there is no active-map value, use Roborock's
            #      numeric flag" — narrower than the code. This is an `elif` on
            #      the branch above, so it ALSO fires when there IS an active-map
            #      value and `len(maps) != 1`, which is the ordinary multi-map
            #      case.
            #   3. "Map <index>" — positional, and undocumented anywhere until
            #      now. It matches no active-map select value and it moves if the
            #      response reorders, so a map keyed this way is undiscoverable
            #      rather than merely unnamed.
            #
            # Someone reconciling a multi-map cache key that came back "Map 3"
            # where they expected the select value is looking at 2 or 3 — not at
            # a bug.
            if active_map_id and len(maps) == 1:
                map_name = active_map_id
            elif map_entry.get("flag") is not None:
                map_name = f"Map {map_entry['flag']}"
            else:
                map_name = f"Map {index}"

        rooms = map_entry.get(rooms_key)
        seg_list: list[dict[str, Any]] = []

        if isinstance(rooms, dict):
            # The Roborock shape: {"16": "KITCHEN", "17": "Dining Room", ...}.
            # id_coercion + name-stripping happen downstream in discovery; keep
            # raw (str) ids here so this shim stays a pure structural transform.
            for raw_id, raw_name in rooms.items():
                if raw_name is None:
                    continue
                seg_list.append({room_id_key: raw_id, room_name_key: raw_name})
        elif isinstance(rooms, list):
            # Already list-of-dicts — pass dict entries through untouched.
            seg_list = [room for room in rooms if isinstance(room, dict)]

        # RP-007 (SRC-3): map NAMES are human-editable and can collide (two maps
        # both named "Main"). The last-writer-wins overwrite silently discarded a
        # whole map's rooms; key collision-safely and say so.
        if map_name in out:
            suffix = (
                f"#flag{map_entry['flag']}" if map_entry.get("flag") is not None
                else f"#idx{index}"
            )
            _LOGGER.warning(
                "room_source: duplicate map name %r in get_maps response for %s; "
                "keying the second as %r",
                map_name, vacuum_entity_id, map_name + suffix,
            )
            map_name = map_name + suffix
        out[map_name] = seg_list

    return out


# ---------------------------------------------------------------------------
# anchor: BN2YZGWK
# Async refresher
# ---------------------------------------------------------------------------

#: Last refresh OUTCOME per vacuum, successes and failures alike.
#:
#: ISSUE #55. The room-source cache only ever recorded SUCCESSES, so a refusal left no
#: trace: diagnostics had to infer "why has this device no rooms" from the shape of its
#: entity list, and inference is how a Roborock Q7 M5 owner got told to go and set his
#: rooms up in the Eufy app. Recording the reason turns a guess into a reading.
DATA_LAST_REFRESH = "room_source_last_refresh"


def record_refresh_outcome(
    hass: HomeAssistant, vacuum_entity_id: str, result: dict[str, Any]
) -> None:
    """Remember one refresh outcome so support surfaces can READ it, not deduce it."""
    store = hass.data.setdefault(DOMAIN, {}).setdefault(DATA_LAST_REFRESH, {})
    store[vacuum_entity_id] = {
        "ok": bool(result.get("ok")),
        "reason": result.get("reason"),
        "at": utc_now_iso(),
    }


def get_last_refresh_outcome(
    hass: HomeAssistant, vacuum_entity_id: str
) -> dict[str, Any]:
    """The last recorded outcome, or {} if this vacuum has never been refreshed.

    ⚠ {} MEANS "NEVER ASKED", NOT "NOTHING WRONG". Those read alike and are opposite,
    so callers must branch on presence before branching on `reason`.
    """
    store = hass.data.get(DOMAIN, {}).get(DATA_LAST_REFRESH) or {}
    return dict(store.get(vacuum_entity_id) or {})


def _refresh_result(ok: bool, reason: str | None) -> dict[str, Any]:
    """Build one refresh outcome.

    ⚠ `refreshed_at` means "this CALL ended ok", NOT "the cache was rewritten",
    and the two are not the same on two of the three ok=True exits. Stated here
    2026-08-24 (RM9) because nothing said it anywhere and the field name asserts
    the opposite.

    Every ok=True exit is stamped with `utc_now_iso()`. Only `reason is None`
    reached `set_cached_room_source`. The other two refreshed nothing:

      - `not_service_source` — an attribute-source brand (Eufy); there is no
        cache entry to write and never was.
      - `superseded_by_newer_refresh` — SRC-4: a newer task won the commit race
        and THIS response was discarded.

    It matters because the whole dict is surfaced verbatim: `setup/workflow.py`
    puts it into the support capture as `room_source_refresh` on the "no map
    detected" path. So a reader diagnosing staleness sees a fresh timestamp that
    does not correspond to the cache's own `refreshed_at` and reasonably
    concludes the source was just re-read.

    Documented rather than repaired on purpose: narrowing the stamp to the
    committing exit changes a published response shape, which is a behaviour
    change and needs its own review. Compare against the cache's
    `get_cached_room_source_with_age` age if you need "when was the cache last
    written".
    """
    return {"ok": ok, "reason": reason, "refreshed_at": utc_now_iso() if ok else None}


async def async_refresh_room_source(
    hass: HomeAssistant,
    vacuum_entity_id: str,
) -> dict[str, Any]:
    """Refresh the cached room source for one vacuum if it uses a service source.

    RP-007 (SRC-1): returns {"ok": bool, "reason": str|None, "refreshed_at": iso|None}
    so callers can tell the EIGHT exits apart instead of every path returning None:

      ok=True,  reason "not_service_source"       - nothing to refresh (always-live)
      ok=False, reason "no_maps_service"          - misdeclared adapter
      ok=False, reason "entity_unavailable"       - device offline/asleep
      ok=False, reason "service_not_supported"    - PERMANENT: the brand integration
                                                    does not implement this call for
                                                    this device; retrying cannot help
      ok=False, reason "service_call_failed"      - upstream call raised (transient)
      ok=False, reason "empty_response_kept_cache"- flattened to nothing; cache kept
      ok=True,  reason "superseded_by_newer_refresh" - a newer commit won the race (SRC-4)
      ok=True,  reason None                       - refreshed and committed

    ⚠ KEEP THE COUNT AND THE LIST IN STEP. (R2-STALE-6: this said "five", listed six,
    and implemented seven — superseded_by_newer_refresh was undocumented. A caller
    enumerating reasons from this list would have treated a legitimate ok=True as an
    unknown state.) `service_not_supported` was added for issue #55 and made it eight.

    The last two ok=False reasons look alike and are opposites: `service_call_failed`
    is "try again", `service_not_supported` is "this will never work on this device".
    Collapsing them is what sent a user to file a bug report about his own hardware's
    documented limits.

    (SRC-4) Concurrent callers coalesce onto one in-flight refresh, and a commit
    generation guarantees a slow stale response never replaces a newer commit.
    """
    config = get_adapter_config(vacuum_entity_id) or {}
    discovery = config.get("discovery") or {}
    if discovery.get("source") != SOURCE_SERVICE_RESPONSE:
        return _refresh_result(True, "not_service_source")

    existing = _INFLIGHT.get(vacuum_entity_id)
    if existing is not None and not existing.done():
        return await asyncio.shield(existing)

    task = hass.loop.create_task(
        _do_refresh_room_source(hass, vacuum_entity_id, config, discovery)
    )
    _INFLIGHT[vacuum_entity_id] = task
    try:
        result = await asyncio.shield(task)
        # Recorded HERE — the one place every service-source exit funnels through, so
        # a new reason cannot be added without being recorded (issue #55).
        record_refresh_outcome(hass, vacuum_entity_id, result)
        return result
    finally:
        if _INFLIGHT.get(vacuum_entity_id) is task:
            _INFLIGHT.pop(vacuum_entity_id, None)


async def _do_refresh_room_source(
    hass: HomeAssistant,
    vacuum_entity_id: str,
    config: dict[str, Any],
    discovery: dict[str, Any],
) -> dict[str, Any]:
    maps_service = discovery.get("maps_service") or {}
    service_domain = maps_service.get("domain")
    service_name = maps_service.get("service")
    if not service_domain or not service_name:
        _LOGGER.debug(
            "room_source: service_response source for %s declares no maps_service; skipping",
            vacuum_entity_id,
        )
        return _refresh_result(False, "no_maps_service")

    # A response-returning entity service raises "did not match any entities" when
    # the target entity is unavailable (e.g. right after a restart, before the
    # brand integration finishes loading, or a Roborock asleep long enough that
    # the integration dropped its entities). Skip cleanly; discovery reads the
    # cached source and dispatch's freshness gate decides whether that is enough.
    state = hass.states.get(vacuum_entity_id)
    if state is not None and state.state in ("unavailable", "unknown"):
        _LOGGER.debug(
            "room_source: %s is %s; skipping %s.%s refresh (using cached source)",
            vacuum_entity_id, state.state, service_domain, service_name,
        )
        return _refresh_result(False, "entity_unavailable")

    generation = _GENERATION.get(vacuum_entity_id, 0)
    try:
        response = await hass.services.async_call(
            service_domain,
            service_name,
            {"entity_id": vacuum_entity_id},
            blocking=True,
            return_response=True,
        )
    except ServiceNotSupported:
        # ISSUE #55. NOT a failure — this is the brand integration stating that THIS
        # DEVICE will never answer, and it will raise identically on every retry.
        #
        # The reporter's Roborock Q7 M5 is a B01-protocol device. Home Assistant routes
        # it to `RoborockQ7Vacuum`, whose `get_maps()` is a stub that raises
        # unconditionally (`components/roborock/vacuum.py`, HA 2026.8) — as does the Q10
        # class. Only the V1 class implements it. B01 devices likewise get no
        # `selected_map` select and no binary sensors at all, which is why that install
        # showed eleven entities and no map anything.
        #
        # Folded into `service_call_failed` this reached the user as "failed … please
        # report it with diagnostics", so he reported it, correctly, doing exactly what
        # we asked. A permanent, correctly-reported "not supported" must never be
        # dressed up as a transient fault with a bug report attached.
        _LOGGER.debug(
            "room_source: %s.%s is not supported for %s; this device cannot provide "
            "a room source and retrying will not change that",
            service_domain, service_name, vacuum_entity_id,
        )
        return _refresh_result(False, "service_not_supported")
    except Exception as err:  # pragma: no cover - upstream service errors are best-effort
        _LOGGER.warning(
            "room_source: %s.%s failed for %s (%s); using cached source",
            service_domain, service_name, vacuum_entity_id, err,
        )
        return _refresh_result(False, "service_call_failed")

    per_map = flatten_maps_response(
        response,
        discovery=discovery,
        vacuum_entity_id=vacuum_entity_id,
        active_map_id=_active_map_id_from_config(hass, config, vacuum_entity_id),
    )
    # RP-006 (SRC-2): a response that flattens to NOTHING must not replace a
    # previously-good cache - a transient upstream glitch would otherwise blank
    # the room source for every consumer until the next successful refresh.
    if not per_map and get_cached_room_source(hass, vacuum_entity_id):
        _LOGGER.warning(
            "room_source: refresh for %s returned no maps; keeping the previous "
            "cached source",
            vacuum_entity_id,
        )
        return _refresh_result(False, "empty_response_kept_cache")
    # (SRC-4) commit only if no newer refresh committed while this one awaited.
    if _GENERATION.get(vacuum_entity_id, 0) != generation:
        _LOGGER.debug(
            "room_source: stale refresh response for %s discarded (a newer refresh "
            "already committed)",
            vacuum_entity_id,
        )
        return _refresh_result(True, "superseded_by_newer_refresh")
    _GENERATION[vacuum_entity_id] = generation + 1
    set_cached_room_source(hass, vacuum_entity_id, per_map)
    _LOGGER.debug(
        "room_source: refreshed %s - %d map(s): %s",
        vacuum_entity_id,
        len(per_map),
        {name: len(rooms) for name, rooms in per_map.items()},
    )
    return _refresh_result(True, None)

"""Resolve a brand's NATIVE current-room signal to a managed room id.

HA-aware (reads a live entity state + the manager's managed-room registry), so it lives
here rather than in ``rooms/utils`` — that module's contract is *pure functions with no HA
or brand dependencies*, which this is not.

TWO consumers ask the SAME question — "which managed room is the robot's live native
current-room?" — and must answer it identically:

  * ``listeners.pose_sampler`` (``source: native_current_room`` attribution) — banks the
    live room for the per-room split.
  * ``mapping.map_source_coordinator`` — fills the map render frame's ``current_room`` that
    the card's current-room HIGHLIGHT draws. A brand whose decoded map leaves ``vacuum_room``
    null (Dreame) has no other source for the highlight, so without this the layer stays dark
    even though the native NAME entity answers the question directly.

A THIRD, DELIBERATELY DIFFERENT variant lives on ``jobs.active_job.ActiveJobTracker.
_resolve_native_target_room_id`` — it matches the job QUEUE, not all managed rooms — for a
dispatched run with known targets. Keep the two apart on purpose: the all-managed match here
is the right answer for an EXTERNAL run and for a HIGHLIGHT, neither of which has a queue to
match against. Collapsing them would reintroduce the exact sibling-drift this module removes.
"""

from __future__ import annotations

from .utils import slugify_room_name


def resolve_native_current_room_id(
    hass, manager, vacuum_entity_id: str, cfg: dict, map_id_str: str
) -> int | None:
    """Resolve the brand's NATIVE current-room NAME (``entities.active_cleaning_target``, e.g.
    Roborock/Dreame ``sensor.<id>_current_room``) to a MANAGED room id on this map, by slug.

    Matches against ALL managed rooms (an external run / a highlight has no job targets to
    match against). Returns None for the dock / a transit room / a sentinel / any name not
    among the managed rooms — a None the callers read as "no confident current room" (transit
    for attribution; no highlight for the map).
    """
    entity_id = (cfg.get("entities", {}) or {}).get("active_cleaning_target")
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None:
        return None
    name = str(getattr(state, "state", "") or "").strip()
    if not name or name.lower() in {"unknown", "unavailable", "none", "null"}:
        return None
    signal_slug = slugify_room_name(name)
    managed = manager.get_managed_rooms(vacuum_entity_id=vacuum_entity_id, map_id=map_id_str)
    rooms = managed.get("rooms", {}) if isinstance(managed, dict) else {}
    for key, room in rooms.items():
        if not isinstance(room, dict):
            continue
        room_slug = (
            str(room.get("slug") or "").strip().lower()
            or slugify_room_name(str(room.get("name") or room.get("room_name") or ""))
        )
        if room_slug and room_slug == signal_slug:
            try:
                return int(room.get("room_id", key))
            except (TypeError, ValueError):
                return None
    return None

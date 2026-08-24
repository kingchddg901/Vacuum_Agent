# 07 — Map Bounds Review (Retired)

!!! danger "This feature does not exist. Nothing on this page is actionable."

    **Map Bounds Review was retired in the mapping split (1.8.0)** and there is no
    replacement control. The learned per-room bounding-box store, its `Map Bounds`
    navigation tab, and its services — `get_room_bounds_snapshot`, `clear_room_bounds`,
    `exclude_room_job_bounds`, `restore_room_job_bounds`, `rebuild_room_bounds_from_archive`
    — were all removed. None of them are registered; calling one fails as an unknown
    service. Room tracking no longer runs in drifting vacuum coordinates at all.

    The page is kept as a landing point for old links and bookmarks, not as
    documentation of a surface you can reach.

The `Map Bounds` tab is not hidden or capability-gated — it is **absent from the
card entirely**. `MAPPING_ARCHIVE` survives only as a legacy string in the `VIEWS`
enum (`src/render-cycle.js`): it is not in `VIEW_ORDER`, so no view root is built for
it and the view router has no case for it, and `main.js` rewrites both `setView` and
the persisted-view restore to Rooms whenever it sees the stored value. A user who
last had the tab open before upgrading lands on Rooms.

## What replaced it

Room presence is driven entirely by the device **native current-room** signal: the
tracker resolves the live room and fires `eufy_vacuum_room_completed` (with per-room
dwell) through a confidence/dwell debounce, and the map card homes off the live map
source's current room. There are no learned coordinate bounds to audit, so there is
nothing for a review surface to operate on.

To review what a run cleaned, see the run review panels in
[User Guide — Review Panels](../user-guide/06-review-panels.md).

For the retired design itself — the trace→bounds algorithm, preserved verbatim so the
approach is not proposed again — see [Room bounds from traces](../dev/history/room-bounds-from-traces.md),
and for the current attribution path see
[Eufy Native Current-Room Transition](../dev/design/shipped/eufy-native-transition.md).

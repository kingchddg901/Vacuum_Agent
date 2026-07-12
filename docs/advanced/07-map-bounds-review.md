# 07 — Map Bounds Review

> **Retired in the mapping split (1.8.0).** The Map Bounds Review feature described on
> this page no longer exists. The learned per-room bounding-box store, its
> `Map Bounds` navigation tab, and its services (snapshot / clear / exclude / restore /
> rebuild-from-archive) were all removed. Room tracking no longer runs in drifting
> vacuum coordinates at all.

Room presence is now driven entirely by the device **native current-room** signal: the
tracker resolves the live room and fires `eufy_vacuum_room_completed` (with per-room
dwell) through a confidence/dwell debounce, and the map card homes off the live map
source's current room. There are no learned coordinate bounds to audit.

To review what a run cleaned, see the run review panels in
[User Guide — Review Panels](../user-guide/06-review-panels.md). For the design and
current state of the native-attribution path, see
[Eufy Native Current-Room Transition](../dev/eufy-native-transition.md).

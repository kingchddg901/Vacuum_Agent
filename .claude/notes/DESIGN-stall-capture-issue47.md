# DESIGN — stall capture: cropped map + position, from issue #47

**Source:** GitHub issue [#47](https://github.com/kingchddg901/Vacuum_Agent/issues/47)
(loryanstrant). They built an automation that notified them when the vacuum had not moved
for ~10 minutes, attaching a cropped map image showing just the room it was in plus its
last known position. Chris asked for their code and said it could be folded in as an
automatic toggle. **Their code has not arrived yet** — this sheet is the scope done
independently, so the two can be compared rather than one anchoring the other.

Status: NOT STARTED. Scoped 2026-08-08. Can ship in its own release; nothing here is
release-gating.

---

## 1. The ruling that shapes everything else

**Position comes from the POSE, never from the `robot_position_x/y` sensors.**
Ruled by Chris 2026-08-08 while scoping this, and it must not be re-derived:

- `adapters/eufy/adapter.py` declares `robot_position_x/y` as
  `sensor.{object_id}_robot_position_{x,y}_raw`. The `_raw` is not decoration. That path
  is the DPS 179 pose in raw device units — uint32, ZUPT-clamped, no IMU — the same source
  the Dirty Seismograph investigation examined and rejected.
- The usable value is **`robot_anchor`**, produced in `mapping/map_source.py:656` (and
  `:908`) via `normalize_rendered(...)`. It is already **normalized 0–1 against the
  rendered image**.

The consequence for this feature is that there is **no transform to write**:

```
marker_px = (robot_anchor[0] * image_width, robot_anchor[1] * image_height)
```

Do **not** reach for `map_source.vacuum_to_normalized()` here. That function is for the
HAZARD layers (virtual walls, forbidden zones, ban-mop zones), which are stored in raw
vacuum coords and must be projected. Using it for the robot routes the position through
exactly the frame this ruling excludes, and it would look correct in review.

---

## 2. What already exists

| need | where | notes |
|---|---|---|
| stall trigger | `EVENT_STALL_DETECTED`, fired in `jobs/active_job.py` | carries `vacuum_entity_id`, `map_id`, **`room_id`**, `room_name`, `elapsed_minutes`, `expected_minutes`, `stall_ratio`; deduped per room per job |
| position | `robot_anchor` (§1) | pre-normalized to the rendered image |
| position HISTORY | `pose_store.py` — 24 h rolling chunked JSONL; `append_sample` / `read_range` / `prune` | the parallel copy that outlives the job; the job buffer dies at the next run on that map |
| room → pixel box | `mapping/mapping_services.py:615` `_bbox_from_polygon_pixel()` | |
| map image entity | declared per brand: Eufy `camera.{object_id}_map`, Roborock `image.{object_id}_{map_slug}` (`live_map_image_entity_pattern`) | **both brands already declare it — build declaration-driven, not Eufy-first** |
| image manipulation | PIL, already imported in `mapping_services` and `adapters/eufy/segmentor.py` | OPTIONAL dependency — see §6 |

## 3. What does not exist

**Fetching the map image inside the integration.** `async_get_image` appears nowhere in
the codebase. This is the only genuinely new capability, and it is two paths because the
two brands publish on different platforms (`camera` vs `image`). Resolve the entity id
from `live_map_image_entity_pattern` — never by constructing it locally.

**Crop + annotate.** PIL crop to the room bbox, draw the position marker, encode PNG.
Small, once §1 and the bbox are in hand.

**Delivery.** Where the PNG lands so an automation can pass it to `notify`. Undecided —
see §7.

---

## 4. The ±30 s ring capture

Chris's addition, 2026-08-08, and the part that makes this more than a screenshot.

On stall, capture the pose ring window around the stall instant, not a single sample:

- **`t-30s` is free.** The ring already holds it; `read_range` returns it immediately.
- **`t+30s` requires waiting.** Schedule a second read at `t+30s` and complete the record
  then. The notification can fire immediately on the backward half rather than waiting.

Why this is worth the extra work:

- **It distinguishes wedged from slow.** `robot_anchor` unchanged across the window is
  real no-movement evidence. A robot that is moving but achieving nothing looks identical
  to a wedged one in the counters and completely different in the ring.
- **It gives the image something to draw.** A trail of the last 30 s of anchors on the
  cropped room says *how* it got stuck — reversing in a corner, or a hard stop.
- **It is the same evidence class the audit kept asking for.** A banked observation beats
  re-derivation; this banks one automatically at the moment it is cheapest to get.

The pose sampler already carries a static-pose dedup guard (`jobs/active_job.py:123` — the
robot repeats an identical pose every tick while parked and unchecked it floods the
buffer). That guard means *identical consecutive anchors may be collapsed*, so the window
reader must reason about sample TIMESTAMPS, not sample COUNT, or a perfectly still robot
will read as "no data" instead of "no movement". This is the one real trap in §4.

---

## 5. Trigger semantics — offer both, do not pick

Ours and theirs are different detectors and neither subsumes the other:

| | detects | misses |
|---|---|---|
| **`EVENT_STALL_DETECTED`** (ours) | elapsed vs expected × ratio for the current room | a robot wedged in a room whose estimate is generous |
| **no movement for N minutes** (theirs) | `robot_anchor` unchanged over a window | a robot moving steadily while achieving nothing |

The pose ring supports theirs directly and it is not much code on top of §4. Cold-start
estimates are also weak right now (the learning store was cleared 2026-08-03), which makes
the ratio detector the less trustworthy of the two *today* specifically.

---

## 6. Degradation — all four are absence-of-evidence traps

The audit's recurring invariant is that absence must not be consumed as evidence. Every
one of these is that shape:

1. **No anchor is not position (0, 0).** `anchor` is deliberately `None` when docked
   (`listeners/pose_sampler.py:218`), and `mapping/map_source_coordinator.py:144` nulls
   `robot_anchor` on a held/stale source. Both correct. A stall handler must treat absent
   as *draw no marker*, never as an origin coordinate.
2. **No polygon is not no image.** A stall in an unsegmented room has no bbox. Fall back
   to the uncropped map; do not send nothing.
3. **No Pillow is not a crash.** numpy/Pillow/scipy are optional (`reqs=[]`); the install
   matrix expects them absent. Hide the feature the way Auto-CV hides its chip, and never
   let it take down the stall path — which is a *job lifecycle* path.
4. **A held/stale map source is not a current one.** If the image is stale, say so or
   refuse; an old map with a fresh marker is the worst possible artifact here.

---

## 7. Open decisions

- **Delivery shape.** File under `www/`, a service response carrying a path, or a field
  added to the stall event. The automation needs something it can hand to `notify`.
  Chris's "automatic toggle" implies the integration writes it unprompted, which argues
  for a file plus the path on the event.
- **Retention.** Written PNGs need a cap or they accumulate silently, which is the exact
  shape of the orphaned-vacuum-keys defect (a set that only ever grew).
- **Whether the ±30 s ring window ships as a separate artifact** (JSON alongside the PNG)
  or only as the drawn trail. The JSON is the more useful debugging artifact and costs
  almost nothing given the ring already exists.

## 8. Testing

Chris can force a stall on real hardware, which makes this cheap to validate end to end —
no need to simulate the trigger. Worth capturing on the FIRST forced stall, because it is
the moment the artifact is most informative:

- the stall event payload as fired,
- the raw ±30 s ring window,
- the produced PNG,

banked together, so the crop geometry and the marker placement can be judged against a
real stuck robot rather than a synthetic one. Both brands eventually; Eufy first is fine
here since the hardware is what gates it, but the IMAGE FETCH must be written
declaration-driven from the start (§2) or Roborock inherits an Eufy-shaped seam.

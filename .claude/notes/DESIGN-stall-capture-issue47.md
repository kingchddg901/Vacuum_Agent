# DESIGN — stall capture: cropped map + position, from issue #47

**Source:** GitHub issue [#47](https://github.com/kingchddg901/Vacuum_Agent/issues/47)
(loryanstrant). They built an automation that notified them when the vacuum had not moved
for ~10 minutes, attaching a cropped map image showing just the room it was in plus its
last known position. Chris asked for their code and said it could be folded in as an
automatic toggle. **Their code has not arrived yet** — this sheet is the scope done
independently, so the two can be compared rather than one anchoring the other.

Status: NOT STARTED. Scoped 2026-08-08. Can ship in its own release; nothing here is
release-gating.

**Scope verdict: this is assembly, not a feature build.** Five of the six components
already exist — trigger, raster, bbox, position, position history — all in one coordinate
space and on both brands. The only genuinely new code is a rasterizer (§3) plus a palette
parity gate (§3b). The design that would have needed a new capability — fetching and
cropping the live camera image — was rejected in favour of rendering from the raster.

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
| **room-id raster, BOTH brands** | Eufy `eufy_room_pixels_v1`; Roborock `decode_roborock_v1_segments()` (`mapping/roborock_raw_map.py:77`) | one resolved room-id **byte per pixel** on both sides |
| **room bbox** | `raster_room_bboxes()`, `mapping/roborock_raw_map.py:229` | returns `{rid: [min_x, min_y, max_x, max_y]}` **normalized 0–1**, and already honours `flip_y` — the SAME rendered frame `robot_anchor` lives in |
| per-room colour override | `room.color` on the room record (`models/models.py:169`) | `"#rrggbb"` or absent |
| theme colour tokens | themes storage carries `tokens`; `themes/preloaded.py` already authors room-fill tokens | |
| image manipulation | PIL, already imported in `mapping_services` and `adapters/eufy/segmentor.py` | OPTIONAL dependency — see §6 |

## 3. Render from the RASTER — do not fetch the camera image

Chris's call, 2026-08-08, and it collapses the scope. The obvious design is to fetch the
live map image and crop it; that needs a capability the integration has never had
(`async_get_image` appears nowhere) on **two different platforms** — Eufy publishes a
`camera` entity, Roborock an `image` entity. It would also have been Eufy-shaped in
practice, since that is the one available to test against.

Rendering from the room-id raster instead needs **no new capability**, and is
brand-agnostic by construction: both brands already produce one resolved room-id byte per
pixel, and `raster_room_bboxes()` already turns that into a normalized per-room box in the
same frame as `robot_anchor`. Mask, crop box, and marker position all fall out of data
that is already computed.

So the only genuinely new code is the rasterizer: crop the byte array to the bbox, map
room-ids to colours, `Image.frombytes`, draw the marker and the §4 trail, encode PNG.

**Performance constraint, already documented in the code.** `raster_room_bboxes` is a
`width × height` Python loop — `map_source_coordinator.py` says so explicitly and notes the
diagnostics call site dispatches it via executor. Do the same here. This is a JOB
LIFECYCLE path; it must never run on the event loop. (Roborock's own decode is the fast
one — a 256-entry `bytes.translate()` LUT, sub-millisecond at ~1M pixels.)

**Naming smell to resolve first.** `raster_room_bboxes` lives in
`mapping/roborock_raw_map.py` but is generic over `{room_pixels, width, height, flip_y}`.
If Eufy's path imports it from a module named for the other brand, that is the shape of
leak this project spent 2026-08-08 removing. Check whether the coupling is real or just
the filename, and move it somewhere brand-neutral if it is the latter.

## 3b. The palette — port the cascade, GATE it, never copy it

The colours must come from the card's existing resolution, not a new invention. The
cascade is defined once in `src/cards/map-room-color.js`:

> per-room override (`room.color`) → theme token `--evcc-room-fill-<N>` → default palette

Two of those three layers are ALREADY backend-readable (`room.color` on the room record;
theme `tokens` in themes storage). Only `ROOM_FILL_PALETTE` — a 12-hex array — is
JS-only. The module is explicitly *"DOM-free except roomFillRgb"* and is ~50 lines of pure
logic (`slot()` modulo wrap, `roomFillTokenName()`, `normalizeHex()`), so it ports to
Python almost line for line.

**But read that file's own header before porting it.** It exists because the SVG fill path
and the raster fill path were *"two BYTE-IDENTICAL hardcoded copies"* that had to be
unified. A Python port is a third copy of the exact thing that already drifted once.

The answer is not to avoid the copy — it is to make the copy unable to drift, which this
repo already has a pattern for: **RF-28's declaration parity gate** (`services.yaml` ↔
schemas ↔ docs). A test asserting the Python palette equals `ROOM_FILL_PALETTE`, failing
the build on divergence, makes a third copy safe. Without that gate, the notification
image quietly stops matching the map the user is looking at, and nothing reports it.

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
   let it take down the stall path — which is a *job lifecycle* path. Note this bites
   harder under §3 than it would have under a camera fetch: rendering the image OURSELVES
   makes Pillow load-bearing rather than incidental.
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

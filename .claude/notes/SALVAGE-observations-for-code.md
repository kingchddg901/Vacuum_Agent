# Salvaged observations owed to the code

Facts recovered from retired documents that **exist nowhere in source** and belong as comments
at the site they explain. Each one was verified absent before being listed — the grep is
recorded so the check can be repeated rather than trusted.

This file grows as the doc rewrite proceeds. Each new document's salvage read appends here;
nothing is applied during a doc pass, so a documentation commit never carries a code change.

**Why these are worth the trouble.** They are physical-world premises — facts about hardware
that no amount of reading the code recovers. The lifecycle salvage examined 23 candidates and
found ZERO, because every one was already carried by a comment that was *richer* than the doc.
Mapping is different: it is the subsystem that touches physical reality, so the observations
that calibrated its constants were never expressible in code.

---

## From `11-mapping-system.md` (retired 2026-08-22)

### 1. Eufy raw position scale — 1 unit ≈ 1 mm, INFERRED

**Site:** `mapping/tracker.py` — extend the existing comment above `MOVEMENT_DELTA_THRESHOLD`.

> The scale is approximately 1 unit ≈ 1 mm for Eufy devices (not verified across all models).

This is what makes `MOVEMENT_DELTA_THRESHOLD = 10.0` readable as *about a centimetre of robot
travel*. Without it the constant is an unscaled number.

⚠ **The trap is that the tree already contains a mm-per-unit statement, and it is Roborock's.**
`mapping/map_source_runtime.py` carries *"coords are vacuum units (1 unit = 1 mm)"* as a
documented Roborock convention, and `adapters/roborock/adapter.py` says `app_zoned_clean` wants
world millimetres. A reader who finds those and generalises them treats the Eufy scale as
guaranteed when it is an unverified approximation. **The Eufy caveat is load-bearing precisely
because the Roborock certainty is nearby.**

*Verified absent:* grep for `1 ?mm|mm/unit|millimet|per unit|vacuum unit` across
`custom_components/`, `src/` and the live docs returns only the three Roborock statements.

### 2. What the Eufy room-mask thresholds are rejecting

**Site:** `adapters/eufy/segmentor.py::_build_room_mask_from_hsv`, at the
`room_mask = (value >= 68) & (saturation >= 18)` line.

> Pixels must be both bright enough (value ≥ 68/255 ≈ 27% brightness) and colourful enough
> (saturation ≥ 18/255 ≈ 7%) to be treated as room pixels. This excludes near-black walls,
> near-white backgrounds, and the off-white dock area.

The threshold *values* are in code. The imagery observation that calibrated them is not — so a
porting brand, or anyone re-tuning, has no statement of what the mask is meant to reject and no
way to tell a mis-tune from a change in how the vendor renders its maps.

*Verified absent:* the function's docstring says only *"Return a binary room-pixel mask derived
from HSV saturation and value thresholds"*; the module says *"tuned for Eufy map colour
palettes"* and *"calibrated on Eufy map images"* — never what they exclude.

### 3. Eufy position frame — axis direction is robot-specific

**Site:** a note is the honest home; if it goes in code, `mapping/tracker.py` near the constants.

> The origin and axis directions are robot-specific. On Eufy map_6 the Y axis increases upward
> in the robot's reference frame but this is not guaranteed by the protocol.

**Low live value, kept for one reason.** The only current consumers of vacuum-space position are
the tracker's Euclidean delta — which is axis-direction agnostic — and the passive dock-drift
log. But `adapters/eufy/adapter.py` deliberately retains `position_lock_reliable` *"against a
possible trace-bounds revival"*, and a revival would need this.

*Verified absent:* the Y-flip comments in `map_source` and `roborock_raw_map` concern the
provider's rendered-image space (0–1, top-left origin), not the raw robot position sensors.

---

## How to apply these

They are comments at a constant, not prose. Each states a **premise** the number rests on, which
is the one thing a reader cannot recover by reading the number. Keep the hedges — *inferred*,
*not verified across models*, *not guaranteed by the protocol* — because the hedge is the fact:
a reader who needs certainty here needs to go and measure, and the comment's job is to tell them
that no one has.

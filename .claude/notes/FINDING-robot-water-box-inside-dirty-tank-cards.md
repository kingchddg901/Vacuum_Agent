# The robot's used-water box is riding inside the dirty-water-tank card

**Status:** MEASURED 2026-09-07, **not fixed** — Chris: *"the robot's water tank shouldn't
be in our maintenance cards. That has slipped through for a long time."* and *"After the
measurement recorded, and we'll fix it afterwards."*

## The finding

35 blocks — **every one a `dirty_water_tank` card** — also service the **robot's** used-water
box. Two different parts, on two different halves of the machine, in one card. Same shape as
the clean/dirty merge, and it has been shipping.

```
34   two-phase   station used-water tank, THEN the robot's used-water box
 1   robot box only    s60_pro
```

## The seam is clean, so the split is mechanical

In all 34 the station phase comes first and is contiguous; the robot-box phase follows and
runs to the end. Example, `z_series`:

```
1-5  [station]    access → remove+open cover → pour → rinse + inner wall → close+refit
6-8  [robot box]  box out → rinse → wipe dry, push back into the robot
```

And the content is **already namespaced** as `dirty.robot_box_*`, so it can be identified by
key prefix without any text matching:

| key | placements |
|---|---|
| `dirty.robot_box_rinse` | 35 |
| `dirty.robot_box_dry_refit` | 34 |
| `dirty.robot_box_out` | 26 |
| `dirty.robot_box_pour` | 17 |
| `dirty.robot_box_cover_close` | 17 |
| `dirty.robot_box_clip_out` | 8 |
| `dirty.robot_box_dry_gate` | 1 |
| `dirty.robot_box_remove_permissive` | 1 |

## The two things that make it a decision, not a sweep

**1. There is no home for the content.** The corpus has exactly two water components,
`clean_water_tank` and `dirty_water_tank`. Nothing for a robot-side water box. So the fix is
either **drop it** or **create a component**, which means a `scope.json` entry and a scope
decision.

**The deciding question is the one that settled the dust box: does the robot's used-water box
have a sensor or a counter?** If it does, it is a card in its own right. If it does not, the
dust-box precedent applies — no operational trigger, and a user holding a full box knows to
empty it.

**2. `s60_pro` would be emptied.** Its entire dirty card *is* the robot's box:

```
off_dock → robot_box_out → robot_box_pour → robot_box_rinse
         → robot_box_cover_close → robot_box_dry_refit
```

No station used-water tank at all. Stripping the robot-box content leaves nothing — which may
be correct, since arguably it never had a `dirty_water_tank` in our sense. It is also the one
family the station-access pass correctly excluded, so it carries no `access.station_tank`
today.

## How it surfaced

Chris spotted it in my own words while I was explaining a *different* defect — I had described
the 34 as "two-phase cards: station tank, then the robot's box" as if that were a normal
shape to have. It is recorded as normal in
[`DESIGN-emit-level-coherence-checks.md`](DESIGN-emit-level-coherence-checks.md), where
`x50_ultra`'s two-phase dirty card is used to explain why a global step order cannot exist.
That explanation is still right about ordering — but nobody asked whether the two phases
should be in one card at all.

## When it is fixed

- strip `dirty.robot_box_*` from the 34, leaving pure station-tank cards
- decide drop vs new component on the sensor question
- decide what `s60_pro` becomes
- the 8 keys are only used here, so a drop retires them cleanly — measure before retiring

# FINDING (live, 2026-08-02) — the card's Cancel button never told the integration

**Found by hardware observation, not audit. Card fix LANDED; two follow-ups open.**
Evidence: `config/eufy_vacuum/learning/alfred/jobs/job_2026-08-01T23-48-48.json`.

## What happened

Chris pressed **Cancel** on the card during a `kitchen -> wait -> entryway` run. The
robot obeyed and docked. The record says the run finished normally:

    was_cancelled:      false
    status:             completed
    lifecycle_state:    completed      lifecycle_message: ""
    used_for_learning:  true           sanity_flags: []
    room_timings:       entryway cleaning_seconds: 30   <- truncated by the cancel

Entryway got 30 s because the run was stopped. Learning recorded 30 s as entryway's
honest cleaning time.

## Root cause — one line, and it was never a bug in the integration

`src/actions/rooms.js` `cancelActiveRun` sent the **stock HA dock command**:

```js
await this.callService("vacuum", "return_to_base", { entity_id: vacuumEntityId });
```

`eufy_vacuum.cancel_active_job` had **ZERO callers anywhere in `src/`**. The robot
obeyed the dock command, so a cancel LOOKED like it worked, but the job tracker was
never told the run ended early. When the robot reached the dock the finalizer saw
"docked, no phases left" and wrote `completed`.

**The asymmetry is the defect's shape:** the card STARTS jobs through the integration
(`start_selected_rooms`, dashboard-card.js:784) and CANCELLED them around it. It opened
the job through the seam and closed it outside the seam.

`async_cancel_active_job` performs the return-to-base **itself** — its docstring:
*"Cancel one tracked job by returning the vacuum to base and finalizing."* So the repair
was a replacement, not a second command.

## Why this one matters to the campaign

RP-010 built a correct cancel chokepoint — single-flight latch, watchdog stopped up
front so it cannot re-dispatch `app_segment_clean` mid-cancel, terminal-state confirm
before the record is written, exactly-once finalize. It landed. It was verified.

**The card had never entered through it.** Every cancel Chris has ever pressed took the
stock HA path around the entire seam.

Same shape as the ADAPTERS audit verdict — *the seam is REAL but not applied* — and the
same shape as the CARD audit verdict, *faithful where it ACTUATES, unfaithful where it
QUALIFIES*, with a sharper edge: here the card was faithful where it actuated (the robot
really did dock) and **silent where it should have recorded**.

It also lands on the north star: the card is meant to open power to non-YAML users, and
the entire cancel lifecycle was reachable only from Developer Tools.

**Neither audit caught it.** Both read the card against its own vocabulary; neither asked
"does the button that says Cancel reach the thing named cancel?" That question — call-site
reachability of a service that exists — is not in any packet's method. Worth adding.

## Blast radius

1. **Every card-initiated cancel in the entire history** is recorded as `completed` with
   `used_for_learning: true`. Not one run — all of them. Truncated room times have been
   training the estimator as honest times for as long as the button has existed.
2. **RP-013c was blocked.** Its before-picture is a cancelled run whose incomplete-run log
   wrongly lists a completed room. No cancel was ever recorded, so no log entry existed to
   be wrong. Capture is possible immediately by calling
   `eufy_vacuum.cancel_active_job` from Developer Tools.
3. `job_2026-08-01T23-48-48` is live pollution — `exclude_learning_job` it.

## Fixed

`src/actions/rooms.js` `cancelActiveRun` now calls `eufy_vacuum.cancel_active_job`
with `vacuum_entity_id` + `map_id` (omitted when unknown; the service resolves the active
map). Reproducer `src/actions/rooms-cancel-through-seam.test.mjs`, CI-gated in
`npm run test:units`. Flip demonstrated: **4 fail -> 0**; CTS-5/CTS-6 pass on both sides
as behavior-preservation guards.

## Still open

**(a) `cancel_detection` is disarmed on its own terms.** The fallback heuristic that
should have caught this:

    "cancel_detection": {
      "cancel_likely": false,
      "reason": "duration_not_short",
      "expected_room_minutes": 0.0,      <- but estimate_snapshot says 1.4
      "short_threshold_minutes": 1.0
    }

`expected_room_minutes` arrives as `0.0` while
`learning_context.estimate_snapshot.estimated_room_minutes_total` in the SAME record says
`1.4`. With expected at zero the bar collapses to the 1.0-minute floor and any run longer
than a minute reads as "not short". Second-order now that the primary path is fixed, but
it is the safety net for external stops (Eufy app, robot button, `vacuum.stop`) and it is
not currently catching anything.

**(b) Dock-during-an-active-job is unhandled.** `dashboard-card.js:789` `_handleDock` is
wired to `dock-btn` and correctly sends `vacuum.return_to_base` — a Dock button SHOULD
dock. But pressing it mid-run reproduces this exact bad record by a different route.
**Design call, not a repair:** refuse while a job runs, prompt ("this will end the run —
cancel it?"), or auto-cancel. Do not silently redirect a Dock button into a cancel.

**(c) `pause_active_job` / `resume_active_job` also have no callers in `src/`.** Not
verified as a defect — the card may simply not offer pause. Worth one read to confirm the
family is not bypassed the same way.

# Backlog-walk NEEDS_CHRIS rulings — 2026-08-24

The walk (wf_3e9e4b2b-2c3) surfaced two items as NEEDS_CHRIS. Chris ruled on
both same-day, before the v2.1.0 tag. Rulings recorded here so the post-drop
execution session doesn't re-ask.

## B33 — MidJobRechargeRateSensor `15→75` window

**Location.** `custom_components/eufy_vacuum/battery/sensors.py:481-485` (docstring);
`custom_components/eufy_vacuum/battery/manager.py:1078` (`_close_session` mid-job
admission — no zone gate today); `manager.py:1102-1108`
(`_classify_session_kind`, tags `mid_job` purely on `_has_active_job`).

**Ruling.** The `15→75` window is not firmware behaviour — it's the
battery-chemistry reading. Cells behave differently outside the constant-current
plateau, and the "cleanest health signal" framing depends on staying inside it.
So the docstring is correct about the physics; the code needs to catch up.

**Action for the post-drop session.** Add a start/end zone gate to
`_close_session` (or wherever mid-job stats admit samples): only sessions whose
`start_battery` sits below the CC-region entry (~15-25%) AND whose `end_battery`
sits above the CC-region exit (~70-80%) contribute to `MidJobRechargeRateSensor`.
Shallow top-ups (60→64) go somewhere else or nowhere. Don't invent a bucket for
them — the sensor exists BECAUSE the CC region is clean; polluting it defeats
the point.

Follow-ups the ruling implies but doesn't decide:
- Exact numeric window. `15→75` is the docstring nominal; the CC region on a
  real Roborock pack sits ~15-80% on most chemistries, but different cells shift
  the shoulders. Measure on Chris's boxes (alfred/ivy/robin) before pinning.
- Whether existing stored samples pre-dating the gate get retro-classified or
  dropped. Default: leave the historical mean as-is, gate at the boundary.
- Whether the shallow-top-up cases get a separate sensor. Chris did not ask
  for one; don't add without discussion.

## SALVAGE_7 — `adapters/eufy/segmentor.py` module framing

**Location.** Top of `custom_components/eufy_vacuum/adapters/eufy/segmentor.py`
(module docstring lacks the framing paragraph).

**Ruling.** The CV path is still load-bearing. It's the tool for **the case
where a map is not available** — the user uploads an image and CV captures the
room shapes from it. `room_pixels` covers the "map is available" case; segmentor
covers the "no map, but the user has an image" case. Not deprecated by
`room_pixels`; it serves a different input path.

**Action for the post-drop session.** Add a framing paragraph near the top of
`segmentor.py` that says outright:

> The CV path handles the case where NO live map is available and the user
> uploads an image of the floor plan instead. `room_pixels` covers the
> live-map case; this file covers the uploaded-image case. Both feed the same
> downstream room-shape consumer. Accuracy bar is 'good enough to be corrected
> in the card', not standalone-correct — the card lets the user snap and adjust
> room outlines after the CV pass, so a 90%-there answer is the goal.

Do NOT frame this as "predates room_pixels" or "predates version control" —
those are historical observations that miss the current-value question. It's
there because it does something room_pixels can't: read an image the user hands
in.

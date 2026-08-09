# DESIGN — Vacuum Agent Maintainer Dev Card

**Status:** PROPOSED (Chris, 2026-08-08) · **Audience:** maintainers only · **Not shipped
with releases.**

> **Design sentence.** The Vacuum Agent Dev Card is a maintainer-only second-screen
> actuator panel for manufacturing rare stimuli while leaving the production system
> responsible for every consequence.

A persistent second-screen control surface for exercising rare, failure-shaped and
timing-sensitive behaviour without waiting for the physical condition to occur.

---

## 1. Problem

The integration increasingly contains behaviour that is slow or inconvenient to reproduce
physically: stall detection and its consequences, pause/resume and failure-return timing,
robot and dock faults, watchdog and lifecycle transitions, stale or missing state, refusal
paths, notification/event consumers.

Most of these conditions can be represented internally once they occur. **Reproducing the
trigger is the expensive part.** Trapping a vacuum under a box is the right test when the
detector is under test, and pure waste when the thing under test is the downstream
pipeline.

So the need is not a simulator. It is a small maintainer actuator panel that exercises
existing seams.

## 2. Core principle

**Manufacture the stimulus. Exercise the real consequences.**

The card must not fake frontend output, nor manufacture the state a subsystem is supposed
to derive.

| | |
|---|---|
| **Good** | pause robot → emit canonical stall event → real consumer runs → real raster read → real pose history → real crop rendered → real notification path |
| **Bad** | draw a fake stall image → show it in a fake notification |

Likewise a failure-return test must not call return-to-base directly if the thing under
test is the machinery that *decides* whether to return. Force the prerequisite; let
production decide.

## 3. Architecture

Deliberately thin. **Backend services own semantics. The card owns buttons.**

The card selects a target vacuum, presents actions, collects only the parameters an action
needs, calls developer services, and displays what came back. It duplicates no domain
logic.

Developer-only services own injection semantics and decide whether an injected condition
is valid and how it enters the production path — e.g. `inject_stall`, `inject_fault`,
`clear_fault`, `advance_clock`, `force_watchdog`, `emit_event`. Exact shape evolves as
useful seams emerge.

**Stopping rule:** if adding an action requires the CARD to understand *why* the action is
valid, that reasoning belongs in the backend.

## 4. Initial control set

Target vacuum selector; everything else acts on it unless explicitly global.

- **Lifecycle** — `PAUSE` / `RESUME` / `CANCEL`, through the same services ordinary
  operation uses.
- **`STALL NOW`** — request a normal pause, let the transition settle, then emit
  `EVENT_STALL_DETECTED` carrying the **real** current job/map/room context. Synchronize
  via the lifecycle contract, not a permanent arbitrary sleep. The rare trigger is
  synthetic; the context is real.
- **Fault injection** — source (robot | dock) + fault, `INJECT` / `CLEAR`. Must enter at
  the canonical fault seam so history, localization, notification, diagnostics and
  error-policy consumers all run normally.
- **Development clock** — `+30s` / `+5m` / `+10m` / `RESET`. **Must not touch the HA host
  clock.** Production keeps asking its normal clock abstraction; dev mode changes the
  answer. Serves pause timeout, failure return, watchdog expiry, stall timing, retry
  windows.

## 5. Safety boundary

The card exists to create abnormal internal conditions, so the line between synthetic
control-plane behaviour and physical dispatch must stay obvious.

**Default rule: developer injection gains no additional permission to command hardware.**

Injecting events, faults, time or internal state is freely available. Any control that can
cause a NEW physical dispatch requires explicit arming that is one-action, auto-expiring,
and never persists across reload/restart. The card must not turn "test a notification"
into "send the vacuum somewhere."

## 6. Observability

Raw output is fine; this is not a product surface. Useful: action, target, result, event
emitted, consumers observed, elapsed, trace id. For the clock: the dev offset AND an
explicit "real clock: unchanged". For faults: whether a canonical fault was created and
which consumers saw it.

## 7. Synthetic vs physical proof — the point of the whole thing

Two questions that should not need the same reproducer:

- **Trigger proof** — does ten minutes of real non-movement make the detector emit the
  right event? May need hardware or a dedicated detector test.
- **Consequence proof** — given a valid stall event, does it capture the right room,
  position, trail, palette and notification? Exercisable repeatedly by injection.

The expensive end-to-end proof shows the seams connect. The card makes each seam
independently cheap. Twenty rendering changes should not mean twenty trips under a box.

## 8. Later: replay

Bank the canonical event or state packet from an interesting real run; offer
`Scenario ▼ → REPLAY`. Same principle — replay the smallest authoritative stimulus, let
current consumers do the rest. Turns one captured field failure into a permanent
regression instrument. Not required for v1.

## 9. What it must not become

A second product UI · a replacement for unit/integration tests · a second implementation
of domain logic · a general HA simulator · a user-facing troubleshooting console · a
catalog of hardcoded scenario semantics.

## 10. Distribution

Outside the release artifact — `dev/vacuum-agent-dev-card.js` or a separate local repo. No
HACS, localization, mobile optimization, user docs, accessibility parity, or
backwards-compatibility promise.

## 11. v1 boundary

Standalone unshipped card · vacuum selector · pause/resume/cancel · `STALL NOW` · canonical
fault inject/clear · scoped dev-clock advance/reset · raw result display · backend services
that enter existing production seams. Everything else waits for a demonstrated need.

**Build list, after the weighing below.** The clock reduced to two actions and one fix:

| # | item | notes |
|---|---|---|
| 1 | `advance_clock` offset reaching `_iso_now()` | not the `now=` param — see the reachability gap |
| 2 | `force_tick` for the six safe pollers | unarmed; broad value for almost no code |
| 3 | press-time reach warning | not a static arming tag — see the §8 correction |

Pause auto-return is exercised by COMPOSING 1 with the existing pause control, not by a
bespoke button. `fire_timer` for the `async_call_later` cases is explicitly out: an offset
cannot serve them and the durations (5 s / 180 s) do not justify a third mechanism.

---

# Verification against the tree — 2026-08-08

Checked while scoping, so the build starts from facts rather than assumptions.

## The seams that already exist

| control | seam | state |
|---|---|---|
| `STALL NOW` | `EVENT_STALL_DETECTED`, fired in `jobs/active_job.py` with `vacuum_entity_id`, `map_id`, `room_id`, `room_name`, `elapsed_minutes`, `expected_minutes`, `stall_ratio` | **exists**; already deduped per room per job |
| lifecycle | pause/resume/cancel services used by ordinary operation | **exists** |
| fault inject | `core/error_tracker` + the adapter-declared `error_tracking` block; codes are canonical enum strings, normalized by `_code_key` | **exists** — inject at the code seam, never at presentation |
| replay (§8) | the recorder-replay corpus (68 real runs, `_crossmatch_replays.py --check`) is already a standing concordance gate | **exists**, and is the natural substrate |

## The development clock — cheaper than it first looks, and it splits in two

A first pass at this concluded "no clock seam exists, `advance_clock` is a prerequisite
refactor across ~16 modules." **That was wrong**, and the correction changes the design.

**Time-dependent behaviour here is two different kinds, and only one is reachable by a
clock offset at all.**

| kind | examples | does a clock offset work? |
|---|---|---|
| **elapsed since a STORED timestamp** | pause auto-return (`paused_at` → now); stall ratio (elapsed vs expected) | **yes** — the decision recomputes from a timestamp on every evaluation |
| **scheduled CALLBACK** | `error_tracker` grace window, `water_amendment` timeout, `debug_capture` autostop — all `async_call_later` | **no.** A scheduled callback fires when it fires; changing what `now()` returns does nothing to it. These need a separate "fire that timer" dev action. |

Conflating the two is the trap: a dev clock that appears to work on pause would silently
do nothing to the grace window, and the failure looks like a bug in the feature under test
rather than in the instrument.

**And the elapsed kind already has its seam.** `ActiveJobTracker`'s pause-timeout check
(`jobs/active_job.py:~2975`) is declared:

```python
def ...(self, *, vacuum_entity_id: str, map_id: str, now: str | None = None):
    ...
    now_dt = self._parse_job_timestamp(now or _iso_now())
    paused_elapsed_seconds = max(int((now_dt - paused_dt).total_seconds()), 0)
```

`now` is **already an injectable parameter**, with `_iso_now()` only as the fallback. So the
dev clock does not need a refactor to reach the pause path — it needs to pass `now`.

Chris's read, 2026-08-08: **pause auto-return is the only FULL clock item we have.** That
matches the code — it is the behaviour whose entire decision is "how long since the stored
timestamp", where the others either recompute from counters or are timer-scheduled.

### Every clock-based behaviour, weighed

The lever that shrinks this: **injection beats time travel wherever the CONSEQUENCE is
what's under test.** `STALL NOW` emits the canonical event, so no amount of clock work is
needed to make the detector fire. A dev clock only earns its keep where the DECISION is
under test and is gated on elapsed time.

| behaviour | mechanism | real wait | offset helps? | verdict |
|---|---|---|---|---|
| **Pause auto-return** | elapsed from `paused_at`, polled 1/min | user-set minutes | **yes** | **BUILD** — the only genuine win |
| Stall / running_long | elapsed vs expected | ~2× a room estimate | moot | already served by injection |
| Battery current window | `now − 14 days` (`CURRENT_WINDOW_DAYS`) | **14 days** | technically | **skip** — a cutoff over stored samples; inject samples with old timestamps, or you only prove the comparison operator works |
| Error grace window | `async_call_later` **5 s** | 5 s | **no** — timer | skip; just wait 5 s |
| Water amendment timeout | `async_call_later` **180 s** default | 3 min | **no** — timer | skip; make the constant declared if it bites |
| External finalize grace | `async_call_later` const | declared | **no** — timer | skip |
| Debug capture autostop | `async_call_later` minutes | user-set | **no** — timer | skip; it is a dev tool already |
| 7 interval pollers | `async_track_time_interval` | ≤ the interval | n/a | `force_tick` — cheap, broad |

Chris's read, 2026-08-08: **pause auto-return is the only full clock item we have.** The
table agrees — everything else is covered by injection, better served by forcing a tick,
or better served by synthetic data.

### Pause is COMPOSED, not a bespoke action

The first draft of this proposed a `force_pause_timeout` button. Rejected, by Chris, in
favour of composing the primitives that already exist:

```
PAUSE (real lifecycle control)  →  advance the dev clock  →  the normal 1-min poller ticks
                                →  production decides, on real elapsed arithmetic
```

This is §2 applied properly. The bespoke button would have manufactured the *decision*; the
composition manufactures only the *stimulus*. It also deletes work — no `force_tick` is
needed for pause, since the natural tick lands within 60 s and the expensive part (the
user-set timeout minutes) is what the offset already removed.

**Reachability gap to fix first.** `get_paused_job_timeout_report` accepts
`now: str | None = None`, but `listeners/pause_timeout.py:61` calls it **without `now`**,
so the check falls back to `_iso_now()`. That parameter is a TEST seam, reachable from a
unit test and not from a button. The offset must therefore land where `_iso_now()` is read
— the difference between "the seam exists" and "the seam exists where the card can reach
it".

### §8 correction — hazard is REACHABILITY, and it is STATE-DEPENDENT

Six of the seven pollers are pure control-plane and need no arming (job progress,
discovery, pose sampler, safety net, hourly, map overlays — Chris's assessment, and they
read state rather than command).

**Pause timeout is not.** Its tick calls `async_cancel_active_job`, and that path
dispatches **`return_to_base`** to the robot (`jobs/active_job.py:2888`, then polls for a
terminal device state). So the consequence of the pause path is a physical dispatch.

Two rules follow, and the second only became visible once actions compose:

1. **Arming attaches to what a control can REACH, not to what it does directly.** The
   pause tick looks exactly like the other six. Classifying controls by their own body
   gets this wrong, and the next control added will get it wrong the same way.
2. **Reach is state-dependent, so it must be evaluated at PRESS TIME.** The same
   `advance clock +10m` is inert with nothing paused and dispatches `return_to_base` with
   a paused job live. There is no static tag that is correct for both. The card should
   say *"you have a paused job — advancing will cancel it and send Alfred home"* rather
   than labelling the button safe or armed up front.

Once actions compose, hazard is a property of the resulting SEQUENCE, not of any button in
it. §5's arming model must be read that way.

## Coupling to the stall-capture design

This card is the development loop for
[DESIGN-stall-capture-issue47](DESIGN-stall-capture-issue47.md), and it constrains that
design in a way worth stating: because `STALL NOW` emits the **canonical** event, the
capture pipeline must hang off `EVENT_STALL_DETECTED` as an ordinary consumer — never off
a private test entry point. If the renderer can only be reached by a path the dev card
invents, the card proves nothing about production.

That is a real design constraint on the renderer's seam, and it arrived before the
renderer was written, which is the cheapest possible moment for it.

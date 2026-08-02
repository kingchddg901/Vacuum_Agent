# Tranche-3 Packets — RF-36: battery / charge estimation (RP-042..RP-045)

> **File renamed 2026-08-01 (was SYNTH-11).** It collided with Fable's
> `SYNTH-11-packets-wave7-card.md`, authored in a parallel session. Wave 7 is
> CARD; this is tranche 3.

**Provenance is different from every other family in this campaign, and that is
the point.** RF-01..RF-35 came from 17 hostile audits and their targeted
siblings. These four came from **watching one charge cycle** on 2026-08-01 while
Ivy sat on a `charge_wait` phase.

`battery/` was NOT unaudited — it was covered by the campaign's direct-read tier
(`corpus/audit-findings-report.md`), the method deliberately chosen for small
subsystems, which found 2 LOW items there. Twenty minutes of live observation
then found four more — a lying default that poisons the session ring, an ETA
that can never re-anchor, and a health metric that reads None on both robots.

So the headline is not a coverage gap. It is **calibration**: what a read of code
at rest can see, versus what only shows up across time and accumulated state.
See the closing section.

Evidence throughout is the LIVE production store
(`.storage/eufy_vacuum.storage`, both vacuums), not reasoning about the code.

---

## RP-042 — An unreadable battery must not be reported as 0 % (RF-36 part 1)

```yaml
packet_id: RP-042
family_id: RF-36
finding_ids: ["live:BAT-1"]
severity: MEDIUM   # was HIGH — see evidence_live; the accumulator is NOT corrupted
files: [custom_components/eufy_vacuum/core/charging.py,
  custom_components/eufy_vacuum/battery/manager.py, tests/]
symbols: [get_battery_level, _update_cycles drain accumulator]
problem: >
  get_battery_level returns a hard 0 when the battery is UNREADABLE. The
  adapter's battery sensor going unavailable/unknown makes _safe_int(state, -1)
  return -1, which falls through to the vacuum entity, whose missing
  battery_level attribute then defaults to 0 (charging.py:56-64). A dropout is
  therefore indistinguishable from a flat pack — and 0 is the most damaging
  value in the domain, because every consumer treats it as "empty".

  This is RP-006's defect class exactly (read_json's lying default) in a different
  file. The signature `-> int` cannot express "unknown", so it invents a reading.

  SCOPE NOTE: the damage is narrower than first written. The drain/cycle
  accumulator is PROTECTED by MAX_DELTA_PCT and its numbers are honest; the
  session ring is not, and that is what this packet repairs. See evidence_live.
evidence_live: >
  CORRECTED 2026-08-01 after Chris asked why the impossible-delta guard did not
  protect the accumulator. IT DOES. An earlier version of this packet claimed the
  dropouts booked ~1.0 phantom cycle each and inflated Alfred's counter ~285 %.
  That was FABRICATED — derived by reasoning from the accumulator code to the
  impossible history rows without checking the guard sitting between them.

  battery/manager.py:526 wraps BOTH the drain accumulator and the rate metrics in
  `if abs(raw_delta) <= MAX_DELTA_PCT`, with MAX_DELTA_PCT = 3.0. A 98-point flip
  fails it, is recorded as `rejected_delta_pct` for post-hoc analysis, and adds
  NOTHING to cumulative_drain_pct. The guard is symmetric: after a dropout leaves
  the anchor at 0, the next real reading of 98 produces +98 and is rejected the
  same way, so there is no phantom charge either.

  MEASURED on the live install, which is what settles it:
      Alfred samples.jsonl — 592 samples, 42 carry rejected_delta_pct,
      and ALL 42 have |delta| > 50. Every dropout was caught; none leaked.
      cumulative_drain_pct = 541.0 (cycles 5.41) is 541 points of REAL drain
      accumulated in <=3 % steps. Ivy 256.0 / 2.56, same story.
  The cycle counter is HONEST. Do not repair it.

  WHAT IS GENUINELY BROKEN — the SESSION RING, which has no such guard.
  _update_session records `end_battery` from the raw reading, so the dropouts
  land there intact:
      Ivy    98 -> 0 in 2.57 min
      Alfred 100 -> 0 in 17.58 / 24.84 / 112.57 / 573.93 min
  A pack cannot shed 98 points in 150 seconds. Four such rows in Alfred's
  50-session ring, two in Ivy's. That ring feeds health_pct and the
  qualifying-session set, which is why RP-045 reads None on both vacuums — so
  this defect and RP-045's symptom share a cause and should land together.

  The ROOT is unchanged and is what this packet fixes: get_battery_level cannot
  say "unknown", so it says 0, and 0 is a plausible-looking battery level that
  every unguarded consumer accepts.

required_behavior: >
  (1) get_battery_level gains an explicit UNKNOWN result. DECIDED BY CHRIS
  2026-08-01: **None (null), NOT a tri-state.** RP-006 needed three states because
  read_json must distinguish ABSENT / CORRUPT / PRESENT, each driving a different
  recovery; a battery reading has only KNOWN and UNKNOWN, so a third would add a
  branch nobody can act on. Use None at every call site. It must never return a
  number it did not read.
  (2) Every consumer decides explicitly. **A None sample is a GAP, not a delta**
  (Chris, 2026-08-01): the drain accumulator and the session recorder SKIP it.
  They must NOT difference against it, and must NOT carry the previous reading
  forward as though it had been observed — a carried-forward reading is the same
  lie as the 0, just quieter.
  (3) REMOVED 2026-08-01. This clause specified a one-shot repair of
  cumulative_drain_pct. **DO NOT DO IT** — the guard already protected that
  counter and the live values are honest (see evidence_live). Repairing it would
  be surgery on a correct, user-visible number.
  What DOES need attention is the SESSION RING, and it belongs with RP-045 rather
  than here: an end_battery of 0 whose start_battery is far above it is not an
  observation, and a session recorder taking the None from (1) must record the
  session as ENDED-UNKNOWN rather than ended-at-zero. Landing (1) stops new bad
  rows; the six existing ones age out of the 50-entry ring on their own.
prohibited_changes: >
  No substring/heuristic fallback for the battery reading (the sibling
  is_charging deliberately refuses one — charging.py:67-75 — and the same
  reasoning applies).
rollback_plan: 2 commits (None + call sites; consumer decisions). The third
  commit was the deleted repair pass.
reproducer_script: NEW _proof_battery_unknown.py — battery sensor unavailable +
  vacuum attribute absent: the READING (before 0 / after None), and the SESSION
  the recorder writes (before ended-at-zero / after ended-unknown). Do NOT write
  a drain-accumulator case: the guard rejects the flip pre-repair, so it would
  report the same shape before and after.
expected_before: ["level=0 on an unreadable sensor",
  "session recorded as ended-at-zero"]
expected_after: ["level=None on an unreadable sensor",
  "session recorded as ended-unknown"]
  # NOT a drain-accumulator assertion — MAX_DELTA_PCT already rejects the flip,
  # so a drain-based case would pass before AND after and prove nothing.
tests_to_add_or_modify: dropout matrix (sensor unavailable / unknown / absent,
  attribute present / absent); accumulator skip; repair-pass idempotence.
superseded_tests: any test asserting get_battery_level returns 0 for a missing
  entity — that IS the defect; update with the decision in the docstring.
broader_gates: full suite.
hardware_gate: none (SOURCE_DECIDABLE) — the live store is already the evidence.
escalation_target: main agent -> Chris
```

---

## RP-043 — The charge ETA must not divide by a frozen rate (RF-36 part 2)

```yaml
packet_id: RP-043
family_id: RF-36
finding_ids: ["live:BAT-2"]
severity: MEDIUM
files: [custom_components/eufy_vacuum/battery/manager.py, tests/]
symbols: [compute_time_to_target_pct precedence, _update_health anchoring]
problem: >
  compute_time_to_target_pct PREFERS the learned baseline (cc/cv_min_per_pct)
  and treats the live zone rate as the degraded fallback. But _update_health
  anchors the baseline only when it is None and NEVER re-anchors, so the
  baseline is frozen at whatever the first qualifying session measured — for
  Alfred, a single session on 2026-06-08. Every Alfred charge ETA since has
  divided by a two-month-old rate, and will keep doing so as the cell ages.

  The fixed baseline is CORRECT for its other job: it is the "when new"
  reference that cc/cv_charge_speed_pct are measured against. One field is
  serving two masters with opposite requirements, and the ETA loses.
evidence_live: >
  Observed 2026-08-01. Ivy has NO baseline (cc/cv null, session_count 0 after 50
  sessions — it never runs below 50 %, so nothing qualifies), so its ETA took the
  zone_rate fallback. First paint quoted a rate carried over from a PREVIOUS
  session and was well off. The first live sample of the current charge
  overwrote rate_high_zone_per_min (manager.py:542-546) and the estimate became
  "very very close" and tracked the taper from there.

  So the fallback converged in ONE sample while the preferred path cannot
  converge at all. The precedence is empirically backwards for this consumer.
required_behavior: >
  Split the two roles. The baseline stays FIXED and keeps feeding
  cc/cv_charge_speed_pct — that is what battery health means and re-anchoring
  would destroy it. compute_time_to_target_pct instead prefers a FRESH zone rate
  and falls back to the baseline when the rate is stale or absent.

  "Fresh" needs a definition in-packet, not left to the implementer: a rate
  observed within this charging session. Sampling is single-interval and can be
  jumpy at a zone boundary or after an HA restart (MAX_RATE_INTERVAL_SEC already
  guards the restart case), so smooth across this session's samples rather than
  trusting the last one alone.
prohibited_changes: >
  Do NOT make the baseline re-anchor. That would fix the ETA by breaking battery
  health, which is the more expensive of the two and cannot be recovered once
  the "when new" reference is lost.
rollback_plan: 1 commit.
reproducer_script: NEW _proof_charge_eta.py — a job on charge_wait with a stale
  baseline and a live zone rate that disagree; assert which one the ETA divides
  by, and that the answer tracks a changing rate.
expected_before: ["eta from frozen baseline", "eta unchanged as live rate moves"]
expected_after: ["eta from fresh session rate", "eta tracks the rate"]
tests_to_add_or_modify: precedence matrix (fresh rate / stale rate / no rate x
  baseline present / absent); smoothing; baseline untouched by ETA changes.
broader_gates: full suite.
hardware_gate: tier 2 ride-along — any charge_wait run; compare the quoted ETA
  against wall-clock. Alfred is the interesting one (it has the frozen baseline).
escalation_target: main agent -> Chris
```

---

## RP-044 — The first ETA of a charge is the least trustworthy one (RF-36 part 3)

```yaml
packet_id: RP-044
family_id: RF-36
finding_ids: ["live:BAT-3"]
severity: LOW
files: [custom_components/eufy_vacuum/battery/manager.py, tests/]
symbols: [compute_time_to_target_pct zone_rate branch]
problem: >
  On the zone_rate path the first ETA of a charge divides by
  rate_high_zone_per_min left over from a PREVIOUS, unrelated charge — which may
  be a 1-minute 99->100 blip (Ivy's stored value was 1.0004 %/min from exactly
  that). The user's first number is systematically the worst one on screen, and
  nothing distinguishes it from the accurate ones that follow.
required_behavior: >
  Treat a carried-over rate as cold-start until THIS session has produced its own
  sample: return minutes=None, source=None. The card already handles that — it
  shows a live wall-clock instead of a fabricated number (the documented
  cold-start behaviour). Reuse that path; do not invent a "provisional" state.
  Depends on RP-043 (same function, same branch) — sequence after it.
rollback_plan: 1 commit, rebases on RP-043.
reproducer_script: extend _proof_charge_eta.py — first call of a new session
  with a stale carried rate.
expected_before: ["first eta from the previous session's rate"]
expected_after: ["first eta None -> wall-clock, then live once sampled"]
tests_to_add_or_modify: first-sample-of-session behaviour; the transition to a
  real number on sample 2.
broader_gates: full suite. hardware_gate: none.
escalation_target: main agent -> Chris
```

---

## RP-045 — Battery health is unreportable on every shipped device (RF-36 part 4)

```yaml
packet_id: RP-045
family_id: RF-36
finding_ids: ["live:BAT-4"]
severity: MEDIUM
files: [custom_components/eufy_vacuum/battery/manager.py,
  custom_components/eufy_vacuum/battery/sensors.py, tests/]
symbols: [_update_health qualifying filter, HEALTH_QUALIFY_START_MAX/END_MIN]
problem: >
  cc_charge_speed_pct, cv_charge_speed_pct and health_pct are computed from
  sessions in the recent-50 ring that start <= 50 % and end >= 90 %. On BOTH
  live vacuums all three read None. Alfred has an anchored baseline from
  2026-06-08 but its anchor session has since rotated out of the ring, so the
  reference survived and the comparison set did not. Ivy never qualifies at all —
  it lives on the dock and its sessions are 100->100, 99->100, 98->98.

  The qualification window describes a discharge pattern these robots do not
  have. A dock-dwelling vacuum can run for months and never once satisfy it, so
  the battery-health sensors ship reading nothing, indefinitely, with no
  indication of why.
evidence_live: >
  vacuum.alfred: baseline anchored (cc 2.6214 / cv 2.6262, 2026-06-08),
    50 sessions, health_pct None, cc_charge_speed_pct None, cv_charge_speed_pct None.
  vacuum.ivy:    baseline empty, 50 sessions, all three None.
required_behavior: >
  Decide and state which of these it is, then implement that:
    (a) the window is too strict -> widen it, and/or accumulate PARTIAL-span
        samples per regime instead of demanding one session spanning both;
    (b) the window is right but the ring is too short -> retain qualifying
        sessions separately from the rolling-50 display ring, so the comparison
        set cannot rotate away from its own anchor;
    (c) the metric is genuinely unavailable for a dock-dwelling device -> the
        sensor must SAY so (an explicit "insufficient data" state plus what
        would satisfy it), not read None forever.
  (b) is at minimum required regardless of the others: a reference outliving its
  comparison set is a bug on any reading.
  Any user-facing string is i18n at creation, all 18 locales.
prohibited_changes: >
  Do not lower the bar so far that health is computed from noise — a 96->100
  session says nothing about pack capacity. Widening must preserve the signal.
rollback_plan: 2 commits (retention/qualification; sensor state + i18n).
reproducer_script: NEW _proof_battery_health.py — a record whose anchor session
  has rotated out of the ring: health None (before) / computed-or-explicit
  (after); plus a dock-dweller history that never qualifies.
expected_before: ["health_pct None with an anchored baseline"]
expected_after: ["health_pct computed, or an explicit insufficient-data state"]
tests_to_add_or_modify: rotation case; dock-dweller case; partial-regime
  accumulation if (a) is chosen.
broader_gates: full suite + npm run check:i18n if a string is added.
hardware_gate: none.
escalation_target: main agent -> Chris
```

---

## The finding behind the findings — the direct-read tier under-detected

**Read this section as WRITTEN 2026-08-01 after four wrong drafts.** Everything
below replaces claims that `battery/` and `sensor/` were unaudited. They were
not. The campaign's coverage record was right and I was re-litigating it from
the wrong artifact each time; the drafts are gone rather than layered, because a
correction stack is unreadable and the wrong version is what gets quoted.

### What the coverage record actually says

`corpus/audit-findings-report.md` carries the coverage table, and the campaign
used a DELIBERATE THREE-TIER strategy scaled to subsystem size:

| tier | scope | cost |
|---|---|---|
| heavyweight hostile audit (8 agents) | #1–#18, the large / contract-dense subsystems | ~1.5–2.0M each |
| 1-agent targeted pass | entity platforms (1,075 LOC) · **sensor leftovers (887)** · infrastructure (1,169) | ~0.17–0.19M each |
| **direct read ×11** | live_refresh · maps · dock · maintenance · counter_segmentation · debug_capture · diagnostics · onboarding · **battery** · **sensor** · setup — **8,709 LOC** | ~0.55M total, ~50K each |

`battery/` and `sensor/` are both named in the direct-read tier, by design,
*because they are small*. `sensor/` additionally got the 1-agent leftovers pass.
Neither was overlooked; both were covered by the method chosen for their size,
and the tiering is the sort of proportionality the campaign should be judged
well for.

### The actual finding, which survives and is more useful

The direct-read tier **under-detected on `battery/`**, measurably:

- ~50K tokens of direct read on `battery/` produced **2 LOW** findings
  (DR-BAT-2/3) plus 2 DOC-ONLY corrections.
- Watching **one** charge cycle produced **four** more: a lying 0-on-unreadable
  default that poisons the session ring, an ETA dividing by a baseline that can
  never re-anchor, a first-quote using the previous session's rate, and a health
  metric reading None on both robots.

  (An earlier draft claimed the default had also inflated the cycle counter
  ~285 %. It had not — `MAX_DELTA_PCT` rejects the flip, verified against 592
  live samples. Corrected in RP-042; the calibration argument below stands
  without it, since all four remaining defects are still time-and-state
  defects a read of code at rest would not surface.)

That is not an argument that nobody looked. It is calibration data about **what a
direct read can and cannot see**, and the pattern is legible: a read inspects
code at rest, so it catches local logic slips (an anchor rewound, a session left
untracked — exactly what DR-BAT-2/3 are) and misses defects that only exist
across TIME and ACCUMULATED STATE — a baseline that never re-anchors, a
qualifying set that rotates out from under its own anchor, a counter poisoned by
a dropout months ago. Those need either a long-horizon adversarial pass or, as
here, live observation.

### So the recommendation changes shape

NOT "audit the unaudited subsystems" — that was wrong and would re-do work.
Instead: **`battery/` is a demonstrated blind spot for the direct-read tier,
so promote it a tier** before executing RF-36, and treat any other direct-read
subsystem carrying long-lived accumulated state (`maintenance/`,
`counter_segmentation/`) as suspect by the same argument.

If the budget for that does not exist, executing RP-042 alone is still
defensible — the accumulator takes fresh damage on every dropout, and stopping
the bleeding does not require the audit to finish first.

### Coverage claim to correct in the campaign record

`project_hostile_audit_calibration` records coverage as "closed except
`mapping/` (~4,251 lines) + segmentor (excluded, empirical CV)". That is
**wrong**: `battery/` and `sensor/` are equally uncovered and were not on the
exclusion list. The gap was invisible because the ledger counts findings, and a
subsystem nobody audited produces no findings — it reads identically to a clean
one. Any future coverage claim should be computed from the audit SCOPES, not
inferred from where findings landed.

